"""
Multi-provider LLM abstraction layer.

Learning goal: Abstract the LLM provider details so agents can switch between
Anthropic Claude, OpenAI, Google Gemini, and local Ollama models without
changing any agent code.

The key pattern: program to an interface (LLMClient), not an implementation.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator

import anthropic
import openai
import structlog

from skellington.core.config import get_settings
from skellington.core.models import ModelCard, get_model_card
from skellington.core.types import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMClient(abc.ABC):
    """
    Abstract base class for all LLM provider clients.

    To add a new provider:
    1. Subclass LLMClient
    2. Implement `complete` and `stream`
    3. Register it in LLMClientFactory
    """

    provider: LLMProvider

    @abc.abstractmethod
    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        """Send messages and return a full (non-streaming) response."""
        ...

    @abc.abstractmethod
    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]:
        """Send messages and yield response tokens as they arrive."""
        ...


# ---------------------------------------------------------------------------
# Anthropic implementation
# ---------------------------------------------------------------------------


def _thinking_param(card: ModelCard, config: LLMConfig) -> dict:
    """Build the thinking block in the form this model accepts.

    budget_tokens was removed on Opus 4.7 and later; sending it returns a 400.
    Adaptive thinking lets the model decide how much to think, which is why
    there is no budget to pass.
    """
    if card.thinking_style == "adaptive":
        return {"type": "adaptive"}
    return {"type": "enabled", "budget_tokens": config.thinking_budget_tokens}


class AnthropicClient(LLMClient):
    """Claude via the Anthropic API."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        headers = (
            {"anthropic-workspace-id": settings.anthropic_workspace_id}
            if settings.anthropic_workspace_id
            else None
        )
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            default_headers=headers,
        )

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        log = logger.bind(provider="anthropic", model=config.model)

        # Separate system messages from conversation
        system = config.system_prompt or ""
        conversation = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]

        kwargs: dict = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": conversation,
        }
        card = get_model_card(config.model)
        if system:
            # System prompts are static per agent — caching them gives ~90%
            # discount on cached tokens after the first call. The block form
            # is required to attach cache_control.
            if card.supports_prompt_caching:
                kwargs["system"] = [
                    {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
                ]
            else:
                kwargs["system"] = system
        if config.tools:
            kwargs["tools"] = config.tools

        if config.prefer_thinking and card.supports_thinking:
            kwargs["thinking"] = _thinking_param(card, config)
        elif card.supports_sampling_params:
            # Anthropic removed temperature from Opus 4.7 onward — sending it
            # is a 400, not a silently ignored field.
            kwargs["temperature"] = config.temperature

        if config.effort is not None and card.supports_effort:
            kwargs["output_config"] = {"effort": config.effort}

        log.debug("sending request")
        response = await self._client.messages.create(**kwargs)
        log.debug("received response", stop_reason=response.stop_reason)

        tool_calls: list[ToolCall] = []
        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        return LLMResponse(
            content=text_content,
            model=config.model,
            provider=self.provider,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
        )

    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]:
        system = config.system_prompt or ""
        conversation = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]
        card = get_model_card(config.model)
        kwargs: dict = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": conversation,
        }
        if card.supports_sampling_params:
            kwargs["temperature"] = config.temperature
        if config.effort is not None and card.supports_effort:
            kwargs["output_config"] = {"effort": config.effort}
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


# ---------------------------------------------------------------------------
# Client decorators
# ---------------------------------------------------------------------------


class FixedSamplingClient(LLMClient):
    """Pins sampling settings on every call routed through this client.

    Agents and subagents each build their own LLMConfig — BaseAgent defaults
    to LLMConfig's 0.7, BaseSubAgent hardcodes 0.3 — and subagents are
    constructed internally, so there is no call site a caller can reach to
    settle a whole run. Wrapping the client reaches all of them:

        client = FixedSamplingClient(LLMClientFactory.create(), effort="low")

    Composes with UsageTrackingClient in either order.

    Note what this cannot do: current Anthropic models removed temperature, so
    pinning it is a no-op there (the client drops it by capability flag). No
    setting makes those models reproducible — effort tunes depth and spend.
    """

    def __init__(
        self,
        inner: LLMClient,
        temperature: float | None = None,
        effort: str | None = None,
    ) -> None:
        self._inner = inner
        self._temperature = temperature
        self._effort = effort
        self.provider = inner.provider

    def _pin(self, config: LLMConfig) -> LLMConfig:
        update: dict = {}
        if self._temperature is not None:
            update["temperature"] = self._temperature
        if self._effort is not None:
            update["effort"] = self._effort
        return config.model_copy(update=update) if update else config

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        return await self._inner.complete(messages, self._pin(config))

    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]:
        async for chunk in self._inner.stream(messages, self._pin(config)):
            yield chunk


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------


class OpenAIClient(LLMClient):
    """GPT-4 and friends via the OpenAI API."""

    provider = LLMProvider.OPENAI

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        conversation = []
        if config.system_prompt:
            conversation.append({"role": "system", "content": config.system_prompt})
        for m in messages:
            conversation.append({"role": m.role.value, "content": m.content})

        kwargs: dict = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": conversation,
        }
        card = get_model_card(config.model)
        if card.supports_sampling_params:
            kwargs["temperature"] = config.temperature
        if config.tools:
            kwargs["tools"] = config.tools

        if config.response_format == "json" and card.supports_native_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""

        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            import json

            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return LLMResponse(
            content=content,
            model=config.model,
            provider=self.provider,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "end_turn",
        )

    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]:
        conversation = []
        if config.system_prompt:
            conversation.append({"role": "system", "content": config.system_prompt})
        for m in messages:
            conversation.append({"role": m.role.value, "content": m.content})

        stream = await self._client.chat.completions.create(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=conversation,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class LLMClientFactory:
    """
    Factory for creating LLM clients.

    Learning goal: Factory pattern + registry for extensible provider support.
    To add a new provider, register it here.
    """

    _registry: dict[LLMProvider, type[LLMClient]] = {
        LLMProvider.ANTHROPIC: AnthropicClient,
        LLMProvider.OPENAI: OpenAIClient,
    }

    @classmethod
    def create(cls, provider: LLMProvider | None = None) -> LLMClient:
        """Create an LLM client for the given provider (or default)."""
        settings = get_settings()
        resolved_provider = provider or settings.default_llm_provider

        client_class = cls._registry.get(resolved_provider)
        if client_class is None:
            raise ValueError(
                f"No client registered for provider '{resolved_provider}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        return client_class()

    @classmethod
    def register(cls, provider: LLMProvider, client_class: type[LLMClient]) -> None:
        """Register a new LLM client implementation."""
        cls._registry[provider] = client_class
