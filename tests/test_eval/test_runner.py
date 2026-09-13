"""Tests for the eval runner."""

from __future__ import annotations

import json

import pytest

from skellington.agents.jack import Jack
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    Task,
    WorkflowState,
)
from skellington.eval import EvalCase, EvalSet, Expect, build_runtime, run_case, run_set


class _StubSpecialist:
    """Stands in for a real specialist, whose subagents have their own protocols."""

    def __init__(self, name: AgentName) -> None:
        self.name = name

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        return AgentResponse(
            agent=self.name, task_id=task.id, content=f"[{self.name.value}] handled it"
        )


def _stub_cast(client) -> list[object]:
    """Jack for real, everyone else stubbed."""
    return [
        Jack(llm_client=client),
        *(
            _StubSpecialist(n)
            for n in (
                AgentName.SALLY,
                AgentName.OOGIE,
                AgentName.ZERO,
                AgentName.LOCK,
                AgentName.SHOCK,
                AgentName.BARREL,
                AgentName.MAYOR,
            )
        ),
    ]


class _ScriptedLLM:
    """Answers planner / router / synthesis based on the system prompt."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self, agent: str = "sally", steps: list[str] | None = None) -> None:
        self._agent = agent
        self._steps = steps or ["build the widget"]
        self.temperatures: list[float] = []

    async def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        self.temperatures.append(config.temperature)
        system = config.system_prompt or ""
        user = messages[-1].content if messages else ""

        if "task planner" in system:
            content = json.dumps(
                {"goal": "g", "steps": self._steps, "estimated_agents": [self._agent]}
            )
        elif "routing expert" in system:
            content = json.dumps(
                {"step": user, "assigned_agent": self._agent, "reasoning": "because"}
            )
        else:
            content = "the widget is built and it is glorious"

        return LLMResponse(
            content=content,
            model=config.model,
            provider=self.provider,
            input_tokens=10,
            output_tokens=4,
        )

    async def stream(self, messages, config):
        yield ""


async def test_run_case_scores_a_real_workflow():
    case = EvalCase(
        id="build",
        request="build the widget",
        expect=Expect(agents=["sally"], succeeded=True, contains=["glorious"]),
    )

    result = await run_case(case, base_client=_ScriptedLLM(), agents_factory=_stub_cast)

    assert result.passed, [c.detail for c in result.checks if not c.passed]
    assert result.trajectory == ["sally"]
    assert result.usage.calls > 0
    assert result.duration_s >= 0


async def test_run_case_records_a_wrong_trajectory_rather_than_raising():
    case = EvalCase(id="build", request="r", expect=Expect(agents=["oogie"]))

    result = await run_case(case, base_client=_ScriptedLLM(agent="sally"), agents_factory=_stub_cast)

    assert not result.passed
    assert result.error is None, "a failed assertion is not a harness error"
    assert result.trajectory == ["sally"]


async def test_an_llm_failure_inside_the_workflow_is_a_failed_case_not_a_harness_error():
    """The Orchestrator catches exceptions from the run by design.

    So an API blowing up mid-workflow is the system failing its case, and it
    is reported through the checks — not as CaseResult.error, which is
    reserved for the harness itself coming apart.
    """

    class _Exploding:
        provider = LLMProvider.ANTHROPIC

        async def complete(self, messages, config):
            raise RuntimeError("the API fell over")

        async def stream(self, messages, config):
            yield ""

    case = EvalCase(id="boom", request="r", expect=Expect(succeeded=True))

    result = await run_case(case, base_client=_Exploding(), agents_factory=_stub_cast)

    assert not result.passed
    assert result.error is None
    succeeded = next(c for c in result.checks if c.name == "succeeded")
    assert "the API fell over" in succeeded.detail


async def test_a_failure_building_the_run_is_reported_as_a_harness_error():
    """Nothing catches this one, so one bad case would otherwise kill the set."""

    def _broken_cast(client):
        raise RuntimeError("could not build the cast")

    case = EvalCase(id="boom", request="r", expect=Expect(succeeded=True))

    result = await run_case(
        case, base_client=_ScriptedLLM(), agents_factory=_broken_cast
    )

    assert not result.passed
    assert result.error is not None
    assert "could not build the cast" in result.error
    assert not result.checks, "a run that never happened has nothing to check"


async def test_temperature_is_pinned_for_every_call_in_the_run():
    llm = _ScriptedLLM()
    case = EvalCase(id="c", request="r", expect=Expect(succeeded=True))

    await run_case(case, base_client=llm, temperature=0.0, agents_factory=_stub_cast)

    assert llm.temperatures, "expected at least one call"
    assert set(llm.temperatures) == {0.0}, (
        "subagents hardcode 0.3 and agents default to 0.7; both must be overridden"
    )


async def test_each_case_gets_its_own_agents():
    """Isolation is the point of injecting agents rather than registering them."""
    eval_set = EvalSet(
        name="s",
        cases=[
            EvalCase(id="one", request="r", expect=Expect(agents=["sally"])),
            EvalCase(id="two", request="r", expect=Expect(agents=["sally"])),
        ],
    )

    report = await run_set(eval_set, base_client=_ScriptedLLM(), agents_factory=_stub_cast)

    assert report.total == 2
    # Usage is per-case, not cumulative: case two must not inherit case one.
    assert report.results[0].usage.calls == report.results[1].usage.calls


async def test_run_set_aggregates_into_a_report():
    eval_set = EvalSet(
        name="routing",
        cases=[
            EvalCase(id="good", request="r", expect=Expect(agents=["sally"])),
            EvalCase(id="bad", request="r", expect=Expect(agents=["oogie"])),
        ],
    )

    report = await run_set(eval_set, base_client=_ScriptedLLM(agent="sally"), agents_factory=_stub_cast)

    assert report.set_name == "routing"
    assert report.passed == 1
    assert report.total == 2
    assert not report.all_passed
    assert report.trajectory_avg == 0.5, "one case scored 1.0, the other 0.0"
    assert report.usage.calls == sum(r.usage.calls for r in report.results)


async def test_only_filters_to_named_cases():
    eval_set = EvalSet(
        name="s",
        cases=[
            EvalCase(id="a", request="r", expect=Expect(agents=["sally"])),
            EvalCase(id="b", request="r", expect=Expect(agents=["sally"])),
        ],
    )

    report = await run_set(eval_set, base_client=_ScriptedLLM(), agents_factory=_stub_cast, only=["b"])

    assert [r.case_id for r in report.results] == ["b"]


async def test_an_unknown_case_id_is_an_error_not_a_silent_no_op():
    eval_set = EvalSet(
        name="s", cases=[EvalCase(id="a", request="r", expect=Expect(agents=["sally"]))]
    )

    with pytest.raises(KeyError, match="typo"):
        await run_set(eval_set, base_client=_ScriptedLLM(), agents_factory=_stub_cast, only=["typo"])


async def test_on_result_reports_progress_as_cases_land():
    seen: list[str] = []
    eval_set = EvalSet(
        name="s",
        cases=[
            EvalCase(id="a", request="r", expect=Expect(agents=["sally"])),
            EvalCase(id="b", request="r", expect=Expect(agents=["sally"])),
        ],
    )

    await run_set(eval_set, base_client=_ScriptedLLM(), agents_factory=_stub_cast, on_result=lambda r: seen.append(r.case_id))

    assert seen == ["a", "b"]


def test_build_runtime_returns_the_full_cast_and_fresh_instances():
    first, _ = build_runtime(base_client=_ScriptedLLM())
    second, _ = build_runtime(base_client=_ScriptedLLM())

    names = {a.name.value for a in first}
    assert {"jack", "sally", "oogie", "zero", "lock", "shock", "barrel", "mayor"} == names
    assert all(a is not b for a, b in zip(first, second, strict=True))
