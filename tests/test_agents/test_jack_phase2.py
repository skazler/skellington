"""Phase 2 integration tests for Jack's orchestration flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skellington.agents.jack import Jack
from skellington.core.types import AgentName, AgentResponse, LLMProvider, Task, WorkflowState
from skellington.subagents.planner import Plan, PlannerSubagent
from skellington.subagents.router import RoutingDecision, RouterSubagent


def _make_llm(content: str = "done"):
    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC  # must be the real enum, not a MagicMock
    llm.complete = AsyncMock(
        return_value=MagicMock(
            content=content,
            tool_calls=[],
            model="test",
            input_tokens=5,
            output_tokens=5,
        )
    )
    return llm


@pytest.fixture
def state():
    return WorkflowState(user_request="test request")


@pytest.fixture
def task():
    return Task(title="test", description="do something useful")


# ---------------------------------------------------------------------------
# PlannerSubagent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_parses_clean_json():
    llm = _make_llm('{"goal": "g", "steps": ["s1", "s2"], "estimated_agents": ["sally"]}')
    planner = PlannerSubagent(llm_client=llm)
    plan = await planner.run("do something")
    assert plan.goal == "g"
    assert plan.steps == ["s1", "s2"]


@pytest.mark.asyncio
async def test_planner_parses_fenced_json():
    llm = _make_llm('```json\n{"goal": "g", "steps": ["s1"], "estimated_agents": []}\n```')
    planner = PlannerSubagent(llm_client=llm)
    plan = await planner.run("do something")
    assert plan.steps == ["s1"]


@pytest.mark.asyncio
async def test_planner_fallback_on_bad_json():
    llm = _make_llm("I cannot produce JSON right now, sorry.")
    planner = PlannerSubagent(llm_client=llm)
    plan = await planner.run("my request")
    # Falls back to treating the whole request as a single step
    assert len(plan.steps) == 1
    assert plan.steps[0] == "my request"


# ---------------------------------------------------------------------------
# RouterSubagent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_parses_clean_json():
    llm = _make_llm('{"step": "build code", "assigned_agent": "sally", "reasoning": "code task"}')
    router = RouterSubagent(llm_client=llm)
    decision = await router.run("build some code")
    assert decision.assigned_agent == "sally"


@pytest.mark.asyncio
async def test_router_fallback_on_unknown_agent():
    llm = _make_llm('{"step": "s", "assigned_agent": "gandalf", "reasoning": "idk"}')
    router = RouterSubagent(llm_client=llm)
    decision = await router.run("some step")
    assert decision.assigned_agent == "mayor"  # fallback


@pytest.mark.asyncio
async def test_router_fallback_on_bad_json():
    llm = _make_llm("nope")
    router = RouterSubagent(llm_client=llm)
    decision = await router.run("some step")
    assert decision.assigned_agent == "mayor"


# ---------------------------------------------------------------------------
# Jack full flow (planner + router mocked out)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jack_orchestrates_and_synthesizes(task, state):
    llm = _make_llm("synthesized final answer")
    jack = Jack(llm_client=llm)

    fixed_plan = Plan(goal="g", steps=["step one", "step two"], estimated_agents=["sally"])
    fixed_decision = RoutingDecision(step="step one", assigned_agent="mayor", reasoning="r")

    with (
        patch.object(PlannerSubagent, "run", AsyncMock(return_value=fixed_plan)),
        patch.object(RouterSubagent, "run", AsyncMock(return_value=fixed_decision)),
    ):
        response = await jack.run(task, state)

    assert response.agent == AgentName.JACK
    assert response.success is True
    # Two steps + two unroutable fallbacks + one synthesis = multiple LLM calls,
    # but the final content comes from the synthesis call
    assert "synthesized final answer" in response.content


@pytest.mark.asyncio
async def test_jack_falls_back_when_planning_fails(task, state):
    llm = _make_llm("direct fallback answer")
    jack = Jack(llm_client=llm)

    with patch.object(PlannerSubagent, "run", AsyncMock(side_effect=RuntimeError("boom"))):
        response = await jack.run(task, state)

    assert response.success is True
    assert "direct fallback answer" in response.content
