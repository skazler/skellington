"""
Multi-provider LLM abstraction layer.

Learning goal: Abstract the LLM provider details so agents can switch between
Anthropic Claude, OpenAI, Google Gemini, and local Ollama models without
changing any agent code.

The key pattern: program to an interface (LLMClient), not an implementation.
"""

from __future__ import annotations

import abc
from typing import AsyncIterator

import anthropic
import openai
import structlog

from skellington.core.config import get_settings
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


class AnthropicClient(LLMClient):
    """Claude via the Anthropic API."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        log = logger.bind(provider="anthropic", model=config.model)

        # Separate system messages from conversation
        system = config.system_prompt or ""
        conversation = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]

        kwargs: dict = dict(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=conversation,
        )
        if system:
            kwargs["system"] = system
        if config.tools:
            kwargs["tools"] = config.tools

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
        kwargs: dict = dict(model=config.model, max_tokens=config.max_tokens, messages=conversation)
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


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

        kwargs: dict = dict(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=conversation,
            temperature=config.temperature,
        )
        if config.tools:
            kwargs["tools"] = config.tools

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
