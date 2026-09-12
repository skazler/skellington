"""Tests for capability-gated request shaping in LLM clients."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.core.types import LLMConfig, LLMProvider, Message, MessageRole


def _stub_anthropic_response() -> MagicMock:
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = []
    response.usage.input_tokens = 1
    response.usage.output_tokens = 1
    return response


def _stub_openai_response() -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = "{}"
    choice.message.tool_calls = None
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    return response


@pytest.mark.asyncio
async def test_anthropic_enables_thinking_when_supported_and_requested(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", prefer_thinking=True)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.messages.create.call_args.kwargs
    assert "thinking" in kwargs
    assert kwargs["thinking"]["type"] == "enabled"


@pytest.mark.asyncio
async def test_anthropic_skips_thinking_when_card_doesnt_support(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-haiku-4-5-20251001", prefer_thinking=True)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.messages.create.call_args.kwargs
    assert "thinking" not in kwargs


@pytest.mark.asyncio
async def test_openai_sets_json_response_format_when_supported(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import OpenAIClient

    config_module.get_settings.cache_clear()
    client = OpenAIClient()
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=_stub_openai_response())

    cfg = LLMConfig(
        provider=LLMProvider.OPENAI, model="gpt-4o", response_format="json"
    )
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_anthropic_caches_system_prompt_when_supported(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", system_prompt="you are a helper")
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.messages.create.call_args.kwargs
    assert isinstance(kwargs["system"], list)
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["system"][0]["text"] == "you are a helper"


@pytest.mark.asyncio
async def test_anthropic_sends_plain_system_when_caching_unsupported(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="some-unknown-model", system_prompt="you are a helper")
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.messages.create.call_args.kwargs
    assert kwargs["system"] == "you are a helper"  # plain string, not a list


@pytest.mark.asyncio
async def test_openai_omits_response_format_when_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import OpenAIClient

    config_module.get_settings.cache_clear()
    client = OpenAIClient()
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock(return_value=_stub_openai_response())

    cfg = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o")  # default text
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


# ---------------------------------------------------------------------------
# Temperature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_passes_temperature_through(monkeypatch):
    """Anthropic dropped config.temperature entirely, so runs were never reproducible."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", temperature=0.0)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    assert client._client.messages.create.call_args.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_anthropic_omits_temperature_when_thinking_is_enabled(monkeypatch):
    """Extended thinking pins temperature to 1; sending both is rejected by the API."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", prefer_thinking=True, temperature=0.0)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    kwargs = client._client.messages.create.call_args.kwargs
    assert "thinking" in kwargs
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_fixed_temperature_client_overrides_whatever_the_caller_built():
    from skellington.core.llm import FixedTemperatureClient
    from skellington.core.types import LLMResponse

    seen: list[float] = []

    class _Inner:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            seen.append(config.temperature)
            return LLMResponse(content="", model=config.model, provider=self.provider)

        async def stream(self, messages, config):
            seen.append(config.temperature)
            yield ""

    client = FixedTemperatureClient(_Inner(), 0.0)

    # BaseAgent's default (0.7) and BaseSubAgent's hardcoded 0.3 both get pinned.
    await client.complete([], LLMConfig(temperature=0.7))
    await client.complete([], LLMConfig(temperature=0.3))
    async for _ in client.stream([], LLMConfig(temperature=0.7)):
        pass

    assert seen == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_fixed_temperature_client_leaves_the_caller_config_untouched():
    from skellington.core.llm import FixedTemperatureClient
    from skellington.core.types import LLMResponse

    class _Inner:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            return LLMResponse(content="", model=config.model, provider=self.provider)

        async def stream(self, messages, config):
            yield ""

    cfg = LLMConfig(temperature=0.7)
    await FixedTemperatureClient(_Inner(), 0.0).complete([], cfg)

    assert cfg.temperature == 0.7, "the override must not mutate the caller's config"
