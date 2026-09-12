"""
Token accounting for a workflow run.

Learning goal: how to measure cost without threading a counter through every
call site. Agents and subagents already accept an injected `llm_client`, and
Jack hands his own client down to the planner and router — so decorating one
client at the top captures every call underneath it.

Usage is recorded per LLM call, which also means a tool-use loop that takes
five turns is counted five times. `BaseAgent.chat` reports only its final
turn's tokens in `AgentResponse.metadata`; these totals do not have that gap.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from skellington.core.llm import LLMClient
from skellington.core.types import (
    LLMConfig,
    LLMResponse,
    Message,
    ModelUsage,
    Usage,
)


class UsageRecorder:
    """Accumulates token counts across every LLM call routed through it."""

    def __init__(self) -> None:
        self._usage = Usage()

    def record(self, response: LLMResponse) -> None:
        self._usage.calls += 1
        self._usage.input_tokens += response.input_tokens
        self._usage.output_tokens += response.output_tokens

        per_model = self._usage.by_model.setdefault(response.model, ModelUsage())
        per_model.calls += 1
        per_model.input_tokens += response.input_tokens
        per_model.output_tokens += response.output_tokens

    def snapshot(self) -> Usage:
        """A detached copy of the totals so far."""
        return self._usage.model_copy(deep=True)


class UsageTrackingClient(LLMClient):
    """Wraps any LLMClient and records what each completion cost.

    Pass one of these as `llm_client=` when building agents and every call
    they or their subagents make lands in the recorder.
    """

    def __init__(self, inner: LLMClient, recorder: UsageRecorder) -> None:
        self._inner = inner
        self._recorder = recorder
        self.provider = inner.provider

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        response = await self._inner.complete(messages, config)
        self._recorder.record(response)
        return response

    async def stream(self, messages: list[Message], config: LLMConfig) -> AsyncIterator[str]:
        # Streaming responses carry no usage block on this path, so there is
        # nothing to record — forward the chunks untouched.
        async for chunk in self._inner.stream(messages, config):
            yield chunk
