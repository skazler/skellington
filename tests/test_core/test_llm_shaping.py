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
    assert kwargs["thinking"] == {"type": "adaptive"}, (
        "budget_tokens was removed on Opus 4.7 and later; sending it is a 400"
    )
    assert "budget_tokens" not in kwargs["thinking"]


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
async def test_anthropic_omits_temperature_when_the_model_removed_it(monkeypatch):
    """Opus 4.7 and later reject sampling params outright — a 400, not a no-op."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", temperature=0.0)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    assert "temperature" not in client._client.messages.create.call_args.kwargs


@pytest.mark.asyncio
async def test_anthropic_passes_temperature_to_models_that_still_take_it(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient
    from skellington.core.models import MODELS, ModelCard

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    older = ModelCard(
        id="claude-legacy",
        provider=LLMProvider.ANTHROPIC,
        context_window=200_000,
        supports_sampling_params=True,
    )
    monkeypatch.setitem(MODELS, "claude-legacy", older)

    cfg = LLMConfig(model="claude-legacy", temperature=0.25)
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    assert client._client.messages.create.call_args.kwargs["temperature"] == 0.25


@pytest.mark.asyncio
async def test_anthropic_sends_effort_when_supported(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient

    config_module.get_settings.cache_clear()
    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    cfg = LLMConfig(model="claude-opus-4-7", effort="low")
    await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)

    assert client._client.messages.create.call_args.kwargs["output_config"] == {"effort": "low"}


@pytest.mark.asyncio
async def test_every_kwarg_we_build_is_accepted_by_the_installed_sdk(monkeypatch):
    """The guard that was missing.

    MagicMock accepts any keyword, so a mock-only test happily asserted a
    parameter the real SDK rejects — which is exactly how `temperature`
    shipped and then blew up on the first live call. Check the kwargs we
    build against the actual signature instead.
    """
    import inspect

    from anthropic.resources.messages import AsyncMessages

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module
    from skellington.core.llm import AnthropicClient
    from skellington.core.models import MODELS

    config_module.get_settings.cache_clear()
    accepted = set(inspect.signature(AsyncMessages.create).parameters)

    client = AnthropicClient()
    client._client = MagicMock()
    client._client.messages.create = AsyncMock(return_value=_stub_anthropic_response())

    for cfg in [
        LLMConfig(model="claude-opus-4-7"),
        LLMConfig(model="claude-opus-4-7", prefer_thinking=True),
        LLMConfig(model="claude-opus-4-7", effort="max"),
        LLMConfig(model="claude-opus-4-7", temperature=0.0),
        *(
            LLMConfig(model=mid, temperature=0.9)
            for mid, card in MODELS.items()
            if card.provider is LLMProvider.ANTHROPIC
        ),
    ]:
        await client.complete([Message(role=MessageRole.USER, content="hi")], cfg)
        sent = set(client._client.messages.create.call_args.kwargs)
        assert sent <= accepted, f"{cfg.model} sent unsupported kwargs: {sent - accepted}"


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
async def test_fixed_sampling_client_overrides_whatever_the_caller_built():
    from skellington.core.llm import FixedSamplingClient
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

    client = FixedSamplingClient(_Inner(), temperature=0.0)

    # BaseAgent's default (0.7) and BaseSubAgent's hardcoded 0.3 both get pinned.
    await client.complete([], LLMConfig(temperature=0.7))
    await client.complete([], LLMConfig(temperature=0.3))
    async for _ in client.stream([], LLMConfig(temperature=0.7)):
        pass

    assert seen == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_fixed_sampling_client_leaves_the_caller_config_untouched():
    from skellington.core.llm import FixedSamplingClient
    from skellington.core.types import LLMResponse

    class _Inner:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            return LLMResponse(content="", model=config.model, provider=self.provider)

        async def stream(self, messages, config):
            yield ""

    cfg = LLMConfig(temperature=0.7)
    await FixedSamplingClient(_Inner(), temperature=0.0).complete([], cfg)

    assert cfg.temperature == 0.7, "the override must not mutate the caller's config"


@pytest.mark.asyncio
async def test_fixed_sampling_client_pins_effort():
    from skellington.core.llm import FixedSamplingClient
    from skellington.core.types import LLMResponse

    seen: list[str | None] = []

    class _Inner:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            seen.append(config.effort)
            return LLMResponse(content="", model=config.model, provider=self.provider)

        async def stream(self, messages, config):
            yield ""

    client = FixedSamplingClient(_Inner(), effort="low")
    await client.complete([], LLMConfig())
    await client.complete([], LLMConfig(effort="max"))

    assert seen == ["low", "low"]


@pytest.mark.asyncio
async def test_fixed_sampling_client_is_a_passthrough_when_nothing_is_pinned():
    from skellington.core.llm import FixedSamplingClient
    from skellington.core.types import LLMResponse

    class _Inner:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            return LLMResponse(content="", model=config.model, provider=self.provider)

        async def stream(self, messages, config):
            yield ""

    cfg = LLMConfig(temperature=0.42, effort="high")
    await FixedSamplingClient(_Inner()).complete([], cfg)

    assert cfg.temperature == 0.42
    assert cfg.effort == "high"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def test_register_tool_wraps_a_bare_json_schema_into_a_tool_definition():
    """Skills export an argument schema, not a whole tool definition.

    Appended raw, its top-level "type": "object" is read by the API as the
    tool's discriminator: 'Input tag object ... does not match any of the
    expected tags'. Every agent with tools failed on its first real call.
    """
    from skellington.core.agent import BaseAgent
    from skellington.core.types import AgentName

    class _Agent(BaseAgent):
        name = AgentName.SALLY

        @property
        def system_prompt(self) -> str:
            return "x"

        async def run(self, task, state):  # pragma: no cover - not exercised
            raise NotImplementedError

    async def do_thing(value: str) -> str:
        """Do the thing.

        Longer explanation that should not reach the description.
        """
        return value

    agent = _Agent(llm_client=MagicMock(provider=LLMProvider.ANTHROPIC))
    agent.register_tool(
        name="do_thing",
        func=do_thing,
        schema={"type": "object", "properties": {"value": {"type": "string"}}},
    )

    definition = agent._tool_schemas[0]
    assert set(definition) == {"name", "description", "input_schema"}
    assert definition["name"] == "do_thing"
    assert definition["description"] == "Do the thing."
    assert definition["input_schema"]["type"] == "object"


def test_register_tool_passes_through_a_complete_definition():
    from skellington.core.agent import BaseAgent
    from skellington.core.types import AgentName

    class _Agent(BaseAgent):
        name = AgentName.SALLY

        @property
        def system_prompt(self) -> str:
            return "x"

        async def run(self, task, state):  # pragma: no cover - not exercised
            raise NotImplementedError

    async def noop() -> None: ...

    complete = {"name": "given", "description": "d", "input_schema": {"type": "object"}}
    agent = _Agent(llm_client=MagicMock(provider=LLMProvider.ANTHROPIC))
    agent.register_tool(name="given", func=noop, schema=complete)

    assert agent._tool_schemas[0] is complete


def test_every_registered_tool_in_the_repo_is_a_valid_definition(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module

    config_module.get_settings.cache_clear()
    from skellington.agents import default_agents

    for agent in default_agents():
        for definition in agent._tool_schemas:
            assert set(definition) >= {"name", "description", "input_schema"}, (
                f"{agent.name.value} registered a malformed tool: {definition}"
            )
            assert definition["input_schema"].get("type") == "object"
