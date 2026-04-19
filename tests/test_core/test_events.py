"""Tests for the Orchestrator event bus — Phase 7 streaming UI."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.agents.jack import Jack
from skellington.core.orchestrator import AgentRegistry, Orchestrator
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMProvider,
    Task,
    TaskStatus,
    WorkflowState,
)


class _FakeAgent:
    """Minimal agent stub for AgentRegistry — just implements .name and .run()."""

    def __init__(self, name: AgentName, *, content: str = "ok", success: bool = True) -> None:
        self.name = name
        self._content = content
        self._success = success

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        return AgentResponse(
            agent=self.name,
            task_id=task.id,
            content=self._content,
            success=self._success,
            error=None if self._success else "boom",
        )


@pytest.fixture(autouse=True)
def _clear_registry():
    """Reset the agent registry around each test."""
    saved = dict(AgentRegistry._agents)
    AgentRegistry._agents.clear()
    yield
    AgentRegistry._agents.clear()
    AgentRegistry._agents.update(saved)


@pytest.mark.asyncio
async def test_emit_is_noop_without_callback():
    """When no on_event is configured, emit should do nothing — not crash."""
    orch = Orchestrator()
    # Should not raise:
    await orch.emit("anything", agent=AgentName.JACK, message="hi")


@pytest.mark.asyncio
async def test_emit_forwards_to_sync_callback():
    events: list[dict[str, Any]] = []
    orch = Orchestrator(on_event=lambda ev: events.append(ev))

    await orch.emit("foo.bar", agent=AgentName.SALLY, message="hi", extra="x")

    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "foo.bar"
    assert ev["agent"] == "sally"
    assert ev["message"] == "hi"
    assert ev["data"] == {"extra": "x"}


@pytest.mark.asyncio
async def test_emit_forwards_to_async_callback():
    events: list[dict[str, Any]] = []

    async def sink(ev: dict[str, Any]) -> None:
        events.append(ev)

    orch = Orchestrator(on_event=sink)
    await orch.emit("workflow.start", message="doing stuff")

    assert events[0]["type"] == "workflow.start"
    assert events[0]["agent"] is None


@pytest.mark.asyncio
async def test_emit_swallows_callback_exceptions():
    """A broken UI callback must never crash the workflow."""

    def broken(_ev: dict[str, Any]) -> None:
        raise RuntimeError("UI exploded")

    orch = Orchestrator(on_event=broken)
    # Must not raise:
    await orch.emit("workflow.start", message="x")


@pytest.mark.asyncio
async def test_run_emits_workflow_start_and_complete_when_jack_missing():
    events: list[dict[str, Any]] = []
    orch = Orchestrator(on_event=lambda ev: events.append(ev))

    await orch.run("do a thing")

    types = [e["type"] for e in events]
    assert "workflow.start" in types
    assert "workflow.complete" in types
    # No Jack registered → workflow.complete reports failure
    complete = next(e for e in events if e["type"] == "workflow.complete")
    assert complete["data"]["success"] is False


@pytest.mark.asyncio
async def test_delegate_emits_agent_lifecycle():
    """Orchestrator.delegate should emit agent.start then agent.complete on success."""
    events: list[dict[str, Any]] = []
    AgentRegistry.register(_FakeAgent(AgentName.SALLY, content="built it"))

    orch = Orchestrator(on_event=lambda ev: events.append(ev))
    state = WorkflowState(user_request="x")
    task = Task(title="do a thing", description="d", assigned_to=AgentName.SALLY)
    state.add_task(task)

    response = await orch.delegate(task, AgentName.SALLY, state)

    assert response.success is True
    types = [e["type"] for e in events]
    assert types == ["agent.start", "agent.complete"]
    assert events[0]["agent"] == "sally"
    assert events[1]["agent"] == "sally"


@pytest.mark.asyncio
async def test_delegate_emits_agent_fail_on_failure():
    events: list[dict[str, Any]] = []
    AgentRegistry.register(_FakeAgent(AgentName.SALLY, content="", success=False))

    orch = Orchestrator(on_event=lambda ev: events.append(ev))
    state = WorkflowState(user_request="x")
    task = Task(title="do a thing", description="d", assigned_to=AgentName.SALLY)
    state.add_task(task)

    await orch.delegate(task, AgentName.SALLY, state)

    types = [e["type"] for e in events]
    assert types == ["agent.start", "agent.fail"]


@pytest.mark.asyncio
async def test_jack_emits_plan_and_route_events(monkeypatch):
    """Jack should emit plan.created and route.decided events during orchestration."""
    from skellington.subagents.planner import Plan
    from skellington.subagents.router import RoutingDecision

    events: list[dict[str, Any]] = []

    # Scripted planner/router so we don't need real LLM calls
    async def fake_plan(self, request):
        return Plan(goal=request, steps=["step one", "step two"], estimated_agents=["sally", "oogie"])

    async def fake_route(self, steps):
        return [
            RoutingDecision(step=steps[0], assigned_agent="sally", reasoning="builds things"),
            RoutingDecision(step=steps[1], assigned_agent="oogie", reasoning="researches things"),
        ]

    monkeypatch.setattr(Jack, "_plan", fake_plan)
    monkeypatch.setattr(Jack, "_route_steps", fake_route)

    async def fake_synthesize(self, task, plan, responses):
        return AgentResponse(agent=self.name, task_id=task.id, content="synthesized", success=True)

    monkeypatch.setattr(Jack, "_synthesize", fake_synthesize)

    AgentRegistry.register(_FakeAgent(AgentName.SALLY, content="built"))
    AgentRegistry.register(_FakeAgent(AgentName.OOGIE, content="researched"))

    # Minimal LLM mock so BaseAgent constructor is happy
    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC
    llm.complete = AsyncMock()

    jack = Jack(llm_client=llm)
    AgentRegistry.register(jack)

    orch = Orchestrator(on_event=lambda ev: events.append(ev))
    await orch.run("please do both")

    types = [e["type"] for e in events]
    assert "workflow.start" in types
    assert "plan.created" in types
    assert types.count("route.decided") == 2
    assert "synthesis.start" in types
    assert "workflow.complete" in types

    plan_event = next(e for e in events if e["type"] == "plan.created")
    assert plan_event["data"]["steps"] == ["step one", "step two"]

    route_events = [e for e in events if e["type"] == "route.decided"]
    assert {e["agent"] for e in route_events} == {"sally", "oogie"}
