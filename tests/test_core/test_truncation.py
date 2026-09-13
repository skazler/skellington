"""Truncated responses must say so, not fail downstream as a parse error."""

from __future__ import annotations

import pytest

from skellington.core.agent import BaseAgent
from skellington.core.llm import TruncatedResponseError
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import (
    AgentName,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
)


class _TruncatingLLM:
    provider = LLMProvider.ANTHROPIC

    def __init__(self, stop_reason: str = "max_tokens") -> None:
        self._stop_reason = stop_reason

    async def complete(self, messages, config) -> LLMResponse:
        return LLMResponse(
            content='{"filename":"demo.py","code":"def reverse(s',
            model=config.model,
            provider=self.provider,
            stop_reason=self._stop_reason,
        )

    async def stream(self, messages, config):
        yield ""


class _Sub(BaseSubAgent[str]):
    name = "probe"
    parent_agent = AgentName.SALLY

    @property
    def system_prompt(self) -> str:
        return "x"

    async def run(self, text: str) -> str:
        return await self._call_llm(text)


class _Agent(BaseAgent):
    name = AgentName.SALLY

    @property
    def system_prompt(self) -> str:
        return "x"

    async def run(self, task, state):  # pragma: no cover - not exercised
        raise NotImplementedError


def test_default_max_tokens_fits_a_generated_source_file():
    """4096 truncated codegen and formatter responses in real runs."""
    assert LLMConfig().max_tokens >= 16000


async def test_subagent_raises_a_named_error_on_truncation():
    with pytest.raises(TruncatedResponseError) as exc:
        await _Sub(llm_client=_TruncatingLLM()).run("go")

    message = str(exc.value)
    assert "max_tokens" in message
    assert "probe" in message, "name the subagent that got cut off"


async def test_subagent_returns_content_normally_when_not_truncated():
    out = await _Sub(llm_client=_TruncatingLLM(stop_reason="end_turn")).run("go")
    assert out.startswith('{"filename"')


async def test_agent_reports_truncation_as_a_failed_response():
    """Agents return AgentResponse rather than raising, so the failure rides along."""
    agent = _Agent(llm_client=_TruncatingLLM())

    response = await agent.chat([Message(role=MessageRole.USER, content="go")])

    assert response.success is False
    assert "max_tokens" in (response.error or "")
    assert response.content, "keep the partial output for debugging"


async def test_agent_succeeds_normally_when_not_truncated():
    agent = _Agent(llm_client=_TruncatingLLM(stop_reason="end_turn"))

    response = await agent.chat([Message(role=MessageRole.USER, content="go")])

    assert response.success is True
