"""Tests for workflow token accounting."""

from __future__ import annotations

from typing import Any

from skellington.agents.jack import Jack
from skellington.core.orchestrator import Orchestrator
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    ModelUsage,
    Task,
    Usage,
    WorkflowState,
)
from skellington.core.usage import UsageRecorder, UsageTrackingClient


class _CountingLLM:
    """Returns a fixed response and reports fixed token counts per call."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self, model: str = "claude-opus-4-7", content: str = "ok") -> None:
        self._model = model
        self._content = content
        self.calls = 0

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=self._content,
            model=config.model or self._model,
            provider=self.provider,
            input_tokens=10,
            output_tokens=3,
        )

    async def stream(self, messages: list[Message], config: LLMConfig):
        yield self._content


class _StubAgent:
    def __init__(self, name: AgentName) -> None:
        self.name = name

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        return AgentResponse(agent=self.name, task_id=task.id, content="done")


async def test_recorder_accumulates_totals_and_per_model_breakdown():
    recorder = UsageRecorder()
    client = UsageTrackingClient(_CountingLLM(), recorder)

    await client.complete([], LLMConfig(model="claude-opus-4-7"))
    await client.complete([], LLMConfig(model="claude-haiku-4-5-20251001"))
    await client.complete([], LLMConfig(model="claude-haiku-4-5-20251001"))

    usage = recorder.snapshot()
    assert usage.calls == 3
    assert usage.input_tokens == 30
    assert usage.output_tokens == 9
    assert usage.total_tokens == 39
    assert usage.by_model["claude-haiku-4-5-20251001"].calls == 2
    assert usage.by_model["claude-opus-4-7"].calls == 1


async def test_tracking_client_forwards_the_inner_response_unchanged():
    inner = _CountingLLM(content="the real answer")
    client = UsageTrackingClient(inner, UsageRecorder())

    response = await client.complete([], LLMConfig())

    assert response.content == "the real answer"
    assert client.provider is inner.provider
    assert inner.calls == 1


async def test_snapshot_is_detached_from_later_recording():
    recorder = UsageRecorder()
    client = UsageTrackingClient(_CountingLLM(), recorder)

    await client.complete([], LLMConfig())
    first = recorder.snapshot()
    await client.complete([], LLMConfig())

    assert first.calls == 1, "snapshot must not mutate as more calls land"
    assert recorder.snapshot().calls == 2


def test_since_reports_only_what_happened_after_the_earlier_snapshot():
    earlier = Usage(calls=2, input_tokens=100, output_tokens=20)
    earlier.by_model["a"] = ModelUsage(calls=2, input_tokens=100, output_tokens=20)

    later = earlier.model_copy(deep=True)
    later.calls = 5
    later.input_tokens = 250
    later.output_tokens = 60
    later.by_model["a"].calls = 5
    later.by_model["a"].input_tokens = 250
    later.by_model["a"].output_tokens = 60

    delta = later.since(earlier)

    assert delta.calls == 3
    assert delta.input_tokens == 150
    assert delta.output_tokens == 40
    assert delta.by_model["a"].calls == 3


def test_since_drops_models_with_no_calls_in_the_window():
    earlier = Usage(calls=1, input_tokens=10, output_tokens=1)
    earlier.by_model["idle"] = ModelUsage(calls=1, input_tokens=10, output_tokens=1)
    later = earlier.model_copy(deep=True)

    assert later.since(earlier).by_model == {}


async def test_workflow_state_carries_usage_for_its_own_run(monkeypatch):
    """Two runs on one recorder must each report only their own tokens."""
    from skellington.subagents.planner import Plan
    from skellington.subagents.router import RoutingDecision

    async def fake_plan(self, request):
        return Plan(goal=request, steps=["one step"], estimated_agents=["sally"])

    async def fake_route(self, steps):
        return [RoutingDecision(step=steps[0], assigned_agent="sally", reasoning="builds")]

    monkeypatch.setattr(Jack, "_plan", fake_plan)
    monkeypatch.setattr(Jack, "_route_steps", fake_route)

    recorder = UsageRecorder()
    client = UsageTrackingClient(_CountingLLM(), recorder)
    orch = Orchestrator(
        agents=[Jack(llm_client=client), _StubAgent(AgentName.SALLY)],
        usage=recorder,
    )

    first = await orch.run("do a thing")
    second = await orch.run("do another thing")

    # Planner and router are stubbed out, so each run makes exactly one real
    # call: Jack's synthesis.
    assert first.usage.calls == 1
    assert first.usage.input_tokens == 10
    assert second.usage.calls == 1, "second run must not inherit the first run's totals"
    assert recorder.snapshot().calls == 2


async def test_usage_defaults_to_zero_when_no_recorder_is_wired():
    orch = Orchestrator(agents=[])
    state = await orch.run("no jack here")

    assert state.usage == Usage()


async def test_workflow_complete_event_carries_usage():
    events: list[dict[str, Any]] = []
    recorder = UsageRecorder()
    orch = Orchestrator(agents=[], usage=recorder, on_event=lambda ev: events.append(ev))

    await orch.run("no jack here")

    complete = next(e for e in events if e["type"] == "workflow.complete")
    assert "usage" in complete["data"]


# ---------------------------------------------------------------------------
# Derived workflow output
# ---------------------------------------------------------------------------


def test_final_output_and_error_derive_from_the_root_task():
    from skellington.core.types import TaskStatus

    state = WorkflowState(user_request="x")
    assert state.final_output is None
    assert state.succeeded is False
    assert state.error == "No tasks created"

    root = Task(title="root", description="x", status=TaskStatus.COMPLETE, result="the answer")
    state.add_task(root)
    assert state.final_output == "the answer"
    assert state.succeeded is True
    assert state.error is None

    root.status = TaskStatus.FAILED
    root.error = "it broke"
    assert state.succeeded is False, "derived, so it must track the root task"
    assert state.error == "it broke"


def test_derived_output_fields_survive_serialization():
    from skellington.core.types import TaskStatus

    state = WorkflowState(user_request="x")
    state.add_task(Task(title="root", description="x", status=TaskStatus.COMPLETE, result="done"))

    dumped = state.model_dump()
    assert dumped["final_output"] == "done"
    assert dumped["succeeded"] is True
    assert dumped["usage"]["calls"] == 0
