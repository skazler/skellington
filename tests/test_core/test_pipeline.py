"""
Pipeline tests: full Plan → Route → Delegate → Synthesize through the real
Orchestrator + Jack + subagent code paths, with the LLM and specialist agents
stubbed at the outer boundary.

These tests catch wiring bugs that per-component tests miss — e.g. agent name
strings the router uses not matching enum values, event ordering invariants,
state accumulation across multiple delegated agents, and error containment.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.agents.jack import Jack
from skellington.core.agent import BaseAgent
from skellington.core.orchestrator import AgentRegistry, Orchestrator
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMProvider,
    Message,
    MessageRole,
    Task,
    TaskStatus,
    ToolCall,
    WorkflowState,
)


# ---------------------------------------------------------------------------
# Test fixtures + helpers
# ---------------------------------------------------------------------------


class _ScriptedLLM:
    """Returns a sequence of pre-baked completions, cycling through them in order.

    Use this when a workflow makes multiple LLM calls (planner, routers,
    synthesis) and you need each to return a different payload.
    """

    provider = LLMProvider.ANTHROPIC

    def __init__(self, scripted_contents: list[str]) -> None:
        self._scripted = scripted_contents
        self._call_count = 0
        self.calls: list[tuple[list[Message], Any]] = []

    async def complete(self, messages, config):
        content = self._scripted[self._call_count % len(self._scripted)]
        self._call_count += 1
        self.calls.append((messages, config))
        return MagicMock(
            content=content,
            tool_calls=[],
            model=config.model,
            input_tokens=5,
            output_tokens=5,
        )


class _RecordingAgent:
    """Specialist agent stub that records that it ran and writes to state.metadata."""

    def __init__(
        self,
        name: AgentName,
        *,
        content: str = "done",
        success: bool = True,
        metadata_section: str | None = None,
    ) -> None:
        self.name = name
        self._content = content
        self._success = success
        self._metadata_section = metadata_section
        self.run_count = 0

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        self.run_count += 1
        if self._metadata_section:
            state.metadata.setdefault(self._metadata_section, {})[str(task.id)] = {
                "ran": True,
                "step": task.description,
            }
        return AgentResponse(
            agent=self.name,
            task_id=task.id,
            content=self._content,
            success=self._success,
            error=None if self._success else "stub-failure",
        )


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(AgentRegistry._agents)
    AgentRegistry._agents.clear()
    yield
    AgentRegistry._agents.clear()
    AgentRegistry._agents.update(saved)


def _script_for_two_step_plan(
    *,
    step_one_agent: str = "sally",
    step_two_agent: str = "oogie",
    synthesis_text: str = "All hallowed and bright!",
) -> list[str]:
    """Build the LLM script for: 1 planner call + 2 router calls + 1 synthesis call."""
    return [
        json.dumps(
            {
                "goal": "do two things",
                "steps": ["build the widget", "research the market"],
                "estimated_agents": [step_one_agent, step_two_agent],
            }
        ),
        json.dumps(
            {
                "step": "build the widget",
                "assigned_agent": step_one_agent,
                "reasoning": "building",
            }
        ),
        json.dumps(
            {
                "step": "research the market",
                "assigned_agent": step_two_agent,
                "reasoning": "researching",
            }
        ),
        synthesis_text,
    ]


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_runs_end_to_end_through_real_subagents():
    """Plan → Route → Delegate → Synthesize with planner+router executing for real."""
    llm = _ScriptedLLM(_script_for_two_step_plan())
    jack = Jack(llm_client=llm)
    sally = _RecordingAgent(AgentName.SALLY, content="widget built")
    oogie = _RecordingAgent(AgentName.OOGIE, content="market researched")

    AgentRegistry.register(jack)
    AgentRegistry.register(sally)
    AgentRegistry.register(oogie)

    events: list[dict[str, Any]] = []
    orch = Orchestrator(on_event=lambda ev: events.append(ev))

    state = await orch.run("build a widget and research its market")

    # Root task succeeded
    root = state.tasks[0]
    assert root.status == TaskStatus.COMPLETE
    assert "hallowed" in (root.result or "").lower()

    # Each specialist ran exactly once
    assert sally.run_count == 1
    assert oogie.run_count == 1

    # Subtasks were tracked under the root
    assert len(state.tasks) >= 3  # root + 2 delegated subtasks


@pytest.mark.asyncio
async def test_pipeline_event_ordering_invariants():
    """workflow.start is first, workflow.complete is last, plan→route→agent→synthesis ordering holds."""
    llm = _ScriptedLLM(_script_for_two_step_plan())
    AgentRegistry.register(Jack(llm_client=llm))
    AgentRegistry.register(_RecordingAgent(AgentName.SALLY))
    AgentRegistry.register(_RecordingAgent(AgentName.OOGIE))

    events: list[dict[str, Any]] = []
    orch = Orchestrator(on_event=lambda ev: events.append(ev))
    await orch.run("do two things")

    types = [e["type"] for e in events]
    assert types[0] == "workflow.start"
    assert types[-1] == "workflow.complete"

    # plan.created must precede every route.decided
    plan_idx = types.index("plan.created")
    first_route = types.index("route.decided")
    assert plan_idx < first_route

    # Every route.decided must precede its corresponding agent.start
    first_agent_start = types.index("agent.start")
    assert first_route < first_agent_start

    # synthesis.start must come after the last agent lifecycle event and before workflow.complete
    last_agent_done = max(i for i, t in enumerate(types) if t in {"agent.complete", "agent.fail"})
    synthesis_idx = types.index("synthesis.start")
    assert last_agent_done < synthesis_idx < types.index("workflow.complete")


@pytest.mark.asyncio
async def test_pipeline_accumulates_state_metadata_from_multiple_agents():
    """Multiple specialist agents in one workflow should each contribute their metadata section."""
    llm = _ScriptedLLM(_script_for_two_step_plan())
    AgentRegistry.register(Jack(llm_client=llm))
    AgentRegistry.register(
        _RecordingAgent(AgentName.SALLY, metadata_section="builds")
    )
    AgentRegistry.register(
        _RecordingAgent(AgentName.OOGIE, metadata_section="research")
    )

    state = await Orchestrator().run("build then research")

    assert "builds" in state.metadata
    assert "research" in state.metadata
    assert len(state.metadata["builds"]) == 1
    assert len(state.metadata["research"]) == 1


@pytest.mark.asyncio
async def test_pipeline_contains_errors_when_one_agent_fails():
    """A single failing agent must not crash the workflow; workflow.complete still fires."""
    llm = _ScriptedLLM(_script_for_two_step_plan())
    AgentRegistry.register(Jack(llm_client=llm))
    AgentRegistry.register(_RecordingAgent(AgentName.SALLY, success=False, content=""))
    AgentRegistry.register(_RecordingAgent(AgentName.OOGIE, content="research ok"))

    events: list[dict[str, Any]] = []
    orch = Orchestrator(on_event=lambda ev: events.append(ev))

    state = await orch.run("build and research, build will fail")

    types = [e["type"] for e in events]
    assert "agent.fail" in types
    assert "agent.complete" in types  # oogie still succeeded
    assert types[-1] == "workflow.complete"
    # The workflow as a whole still completes — Jack synthesizes whatever partial results came back
    assert state.tasks[0].status == TaskStatus.COMPLETE


@pytest.mark.asyncio
async def test_pipeline_survives_router_fallback_to_unregistered_agent():
    """When the LLM names an unknown agent, RouterSubagent falls back to mayor.
    If mayor isn't registered either, the orchestrator returns a failed response
    for that step — but the workflow as a whole still completes."""
    script = [
        json.dumps(
            {"goal": "g", "steps": ["weird step"], "estimated_agents": ["gandalf"]}
        ),
        json.dumps(
            {"step": "weird step", "assigned_agent": "gandalf", "reasoning": "wizard work"}
        ),
        "synthesized despite the chaos",
    ]
    llm = _ScriptedLLM(script)
    AgentRegistry.register(Jack(llm_client=llm))
    # Note: no mayor registered — router will fall back to mayor and delegation fails

    events: list[dict[str, Any]] = []
    state = await Orchestrator(on_event=lambda ev: events.append(ev)).run("do a weird thing")

    types = [e["type"] for e in events]
    assert state.tasks[0].status == TaskStatus.COMPLETE
    assert types[-1] == "workflow.complete"
    assert "synthesis.start" in types
    # Note: Orchestrator.delegate() currently early-returns without emitting
    # agent.start/agent.fail when the target agent isn't registered. If that's
    # ever fixed, this test should additionally assert "agent.fail" in types.


# ---------------------------------------------------------------------------
# BaseAgent tool-use loop (currently uncovered by direct tests)
# ---------------------------------------------------------------------------


class _ToolyAgent(BaseAgent):
    """Concrete BaseAgent subclass with a single registered tool, for testing chat()."""

    name = AgentName.SALLY

    @property
    def system_prompt(self) -> str:
        return "test"

    async def run(self, task, state):  # pragma: no cover — not exercised
        raise NotImplementedError


@pytest.mark.asyncio
async def test_base_agent_chat_executes_tool_calls_and_loops():
    """chat() should call tools that the LLM requests and feed results back in a follow-up turn."""
    call_log: list[dict[str, Any]] = []

    async def fake_tool(**kwargs):
        call_log.append(kwargs)
        return "tool-output-42"

    # LLM call #1 requests a tool; call #2 returns a final answer
    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC
    llm.complete = AsyncMock(
        side_effect=[
            MagicMock(
                content="thinking...",
                tool_calls=[ToolCall(id="t1", name="my_tool", arguments={"q": "hi"})],
                model="test",
                input_tokens=5,
                output_tokens=5,
            ),
            MagicMock(
                content="final answer",
                tool_calls=[],
                model="test",
                input_tokens=5,
                output_tokens=5,
            ),
        ]
    )

    agent = _ToolyAgent(llm_client=llm)
    agent.register_tool(name="my_tool", func=fake_tool, schema={"name": "my_tool"})

    response = await agent.chat([Message(role=MessageRole.USER, content="go")])

    assert response.content == "final answer"
    assert response.metadata["iterations"] == 2
    assert call_log == [{"q": "hi"}]


@pytest.mark.asyncio
async def test_base_agent_chat_hits_max_iterations_when_llm_never_settles():
    """If the LLM keeps requesting tools forever, chat() should bail rather than spin."""

    async def fake_tool(**_):
        return "still going"

    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC
    llm.complete = AsyncMock(
        return_value=MagicMock(
            content="more please",
            tool_calls=[ToolCall(id="t", name="my_tool", arguments={})],
            model="test",
            input_tokens=1,
            output_tokens=1,
        )
    )

    agent = _ToolyAgent(llm_client=llm)
    agent.register_tool(name="my_tool", func=fake_tool, schema={"name": "my_tool"})

    response = await agent.chat([Message(role=MessageRole.USER, content="go")])

    assert response.success is False
    assert response.error == "max_iterations_exceeded"
