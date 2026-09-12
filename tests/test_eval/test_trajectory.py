"""Tests for scoring a run against a case."""

from __future__ import annotations

import pytest

from skellington.core.types import Task, TaskStatus, Usage, WorkflowState
from skellington.eval import (
    EvalCase,
    Expect,
    agent_trajectory,
    lifecycle_violations,
    routed_agents,
    score,
    trajectory_score,
)


def _ev(type_: str, agent: str | None = None, **data) -> dict:
    return {"type": type_, "agent": agent, "message": "", "data": data}


def _clean_stream(*agents: str) -> list[dict]:
    """A well-formed stream delegating to each agent in turn."""
    events = [_ev("workflow.start"), _ev("plan.created")]
    for agent in agents:
        events += [
            _ev("route.decided", agent),
            _ev("agent.start", agent),
            _ev("agent.complete", agent),
        ]
    events += [_ev("synthesis.start"), _ev("workflow.complete")]
    return events


def _state(output: str = "an answer", status: TaskStatus = TaskStatus.COMPLETE) -> WorkflowState:
    state = WorkflowState(user_request="x")
    state.add_task(Task(title="root", description="x", status=status, result=output))
    return state


# ---------------------------------------------------------------------------
# Reading the stream
# ---------------------------------------------------------------------------


def test_trajectory_reads_agent_start_in_order():
    events = _clean_stream("oogie", "sally", "mayor")
    assert agent_trajectory(events) == ["oogie", "sally", "mayor"]


def test_trajectory_includes_failed_delegations():
    """A step that was attempted and failed is still part of the trajectory."""
    events = [
        _ev("workflow.start"),
        _ev("agent.start", "lock"),
        _ev("agent.fail", "lock"),
        _ev("workflow.complete"),
    ]
    assert agent_trajectory(events) == ["lock"]


def test_routed_agents_and_trajectory_diverge_when_jack_absorbs_a_step():
    """route.decided fires for steps Jack handles himself; agent.start does not."""
    events = [
        _ev("workflow.start"),
        _ev("route.decided", "jack"),
        _ev("route.decided", "sally"),
        _ev("agent.start", "sally"),
        _ev("agent.complete", "sally"),
        _ev("workflow.complete"),
    ]
    assert routed_agents(events) == ["jack", "sally"]
    assert agent_trajectory(events) == ["sally"]


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_clean_stream_has_no_violations():
    assert lifecycle_violations(_clean_stream("sally", "oogie")) == []


def test_a_start_without_a_terminal_is_caught():
    """This is the pre-fix delegate() bug: a dropped step must not score as a pass."""
    events = [
        _ev("workflow.start"),
        _ev("agent.start", "lock"),
        _ev("workflow.complete"),
    ]
    problems = lifecycle_violations(events)
    assert any("dropped or double-reported" in p for p in problems)


def test_interleaved_lifecycles_are_caught():
    events = [
        _ev("workflow.start"),
        _ev("agent.start", "sally"),
        _ev("agent.start", "oogie"),
        _ev("agent.complete", "oogie"),
        _ev("agent.complete", "sally"),
        _ev("workflow.complete"),
    ]
    assert any("still open" in p for p in lifecycle_violations(events))


def test_truncated_stream_is_caught():
    events = [_ev("workflow.start"), _ev("plan.created")]
    assert any("expected workflow.complete" in p for p in lifecycle_violations(events))


# ---------------------------------------------------------------------------
# Trajectory scoring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected,actual,want",
    [
        (["a", "b"], ["a", "b"], 1.0),
        (["a", "b"], ["a", "c"], 0.5),
        (["a", "b"], ["b", "a"], 0.0),
        (["a", "b"], ["a"], 0.5),
        (["a"], ["a", "b"], 0.5),
        ([], [], 1.0),
        ([], ["a"], 0.0),
    ],
)
def test_trajectory_score_positions(expected, actual, want):
    assert trajectory_score(expected, actual) == want


def test_extra_steps_are_penalised_not_ignored():
    """Scoring against len(expected) alone would call this perfect."""
    assert trajectory_score(["a"], ["a", "b", "c"]) < 1.0


# ---------------------------------------------------------------------------
# Whole-case scoring
# ---------------------------------------------------------------------------


def test_a_fully_matching_run_passes():
    case = EvalCase(
        id="c",
        request="r",
        expect=Expect(agents=["oogie", "sally"], succeeded=True, contains=["answer"]),
    )
    result = score(case, _state(), _clean_stream("oogie", "sally"))

    assert result.passed
    assert result.trajectory == ["oogie", "sally"]
    assert result.trajectory_score == 1.0


def test_wrong_trajectory_fails_the_case_and_reports_both_sides():
    case = EvalCase(id="c", request="r", expect=Expect(agents=["oogie", "sally"]))
    result = score(case, _state(), _clean_stream("sally", "oogie"))

    assert not result.passed
    check = next(c for c in result.checks if c.name == "trajectory")
    assert check.score == 0.0
    assert "expected ['oogie', 'sally']" in check.detail
    assert "got ['sally', 'oogie']" in check.detail


def test_excludes_catches_forbidden_output():
    case = EvalCase(id="c", request="r", expect=Expect(excludes=["Traceback"]))
    state = _state(output="boom: Traceback (most recent call last)")

    result = score(case, state, _clean_stream("sally"))

    assert not result.passed


def test_substring_checks_are_case_insensitive():
    case = EvalCase(id="c", request="r", expect=Expect(contains=["ANSWER"]))
    assert score(case, _state(output="an answer"), _clean_stream("sally")).passed


def test_cost_ceilings_are_enforced():
    case = EvalCase(id="c", request="r", expect=Expect(max_llm_calls=2, max_total_tokens=100))
    state = _state()
    state.usage = Usage(calls=5, input_tokens=90, output_tokens=40)

    result = score(case, state, _clean_stream("sally"))

    assert not result.passed
    assert not next(c for c in result.checks if c.name == "max_llm_calls").passed
    assert not next(c for c in result.checks if c.name == "max_total_tokens").passed


def test_a_broken_stream_fails_even_a_case_that_only_checks_output():
    """A case cannot opt out of the orchestrator's own contract."""
    case = EvalCase(id="c", request="r", expect=Expect(contains=["answer"]))
    events = [_ev("workflow.start"), _ev("agent.start", "lock"), _ev("workflow.complete")]

    result = score(case, _state(), events)

    assert not result.passed
    assert not next(c for c in result.checks if c.name == "event_stream").passed


def test_a_failed_workflow_reports_why():
    case = EvalCase(id="c", request="r", expect=Expect(succeeded=True))
    state = WorkflowState(user_request="x")
    state.add_task(
        Task(title="root", description="x", status=TaskStatus.FAILED, error="it broke")
    )

    result = score(case, state, _clean_stream("sally"))

    assert not result.passed
    assert "it broke" in next(c for c in result.checks if c.name == "succeeded").detail


# ---------------------------------------------------------------------------
# Step failures
# ---------------------------------------------------------------------------


def _stream_with_failure() -> list[dict]:
    """Jack's real shape when a step fails: he synthesizes the rest and reports success."""
    return [
        _ev("workflow.start"),
        _ev("plan.created"),
        _ev("route.decided", "sally"),
        _ev("agent.start", "sally"),
        _ev("agent.complete", "sally"),
        _ev("route.decided", "lock"),
        _ev("agent.start", "lock"),
        _ev("agent.fail", "lock"),
        _ev("synthesis.start"),
        _ev("workflow.complete"),
    ]


def test_a_failed_step_fails_the_case_by_default():
    """Every other check passes here — this is the only one that catches it.

    The trajectory still lists lock (it was attempted), the stream is still
    well formed, and Jack still reports success off the partial results.
    """
    case = EvalCase(id="c", request="r", expect=Expect(agents=["sally", "lock"], succeeded=True))

    result = score(case, _state(), _stream_with_failure())

    assert not result.passed
    assert result.trajectory_score == 1.0
    assert next(c for c in result.checks if c.name == "event_stream").passed
    assert next(c for c in result.checks if c.name == "succeeded").passed
    failure = next(c for c in result.checks if c.name == "no_step_failures")
    assert not failure.passed
    assert "lock" in failure.detail


def test_a_case_can_opt_into_tolerating_failures():
    case = EvalCase(
        id="c",
        request="r",
        expect=Expect(agents=["sally", "lock"], allow_step_failures=True),
    )

    result = score(case, _state(), _stream_with_failure())

    assert result.passed
    assert not any(c.name == "no_step_failures" for c in result.checks)


def test_clean_runs_report_the_check_as_passing():
    case = EvalCase(id="c", request="r", expect=Expect(agents=["sally"]))
    result = score(case, _state(), _clean_stream("sally"))

    assert next(c for c in result.checks if c.name == "no_step_failures").passed
