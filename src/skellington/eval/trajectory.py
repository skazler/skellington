"""
Scoring a workflow run against a case's expectations.

Learning goal: the orchestrator already emits a typed event for every
decision it makes, so grading a run is reading that stream — no LLM, no
heuristics, no parsing of prose. Everything in this module is a pure
function over `list[dict]` plus the final WorkflowState.

Why the event stream rather than the final answer: two runs can produce
equally good prose while routing completely differently. For an orchestrator
the routing *is* the behavior under test, and a wrong route that still reads
well is exactly the regression an output-only score misses.
"""

from __future__ import annotations

from typing import Any

from skellington.core.types import WorkflowState
from skellington.eval.types import CaseResult, Check, EvalCase

Event = dict[str, Any]


# ---------------------------------------------------------------------------
# Reading the stream
# ---------------------------------------------------------------------------


def agent_trajectory(events: list[Event]) -> list[str]:
    """The specialists actually delegated to, in order.

    Taken from agent.start rather than route.decided because it reports what
    ran, not what was intended. The two diverge when Jack handles a step
    himself — an unroutable agent name, or a router that assigned back to
    Jack — which emits route.decided but never reaches delegate().
    """
    return [e["agent"] for e in events if e["type"] == "agent.start" and e.get("agent")]


def routed_agents(events: list[Event]) -> list[str]:
    """What the router decided, in order, including steps Jack then absorbed."""
    return [e["agent"] for e in events if e["type"] == "route.decided" and e.get("agent")]


def failed_agents(events: list[Event]) -> list[str]:
    """Agents whose step ended in agent.fail."""
    return [e["agent"] for e in events if e["type"] == "agent.fail" and e.get("agent")]


def failure_reasons(events: list[Event]) -> list[str]:
    """"agent: why" for each failed step.

    Which agent failed is rarely enough to act on — a report that says only
    "mayor failed" sends you back for another full run to find out why.
    """
    return [
        f"{e['agent']}: {e.get('message') or 'no reason reported'}"
        for e in events
        if e["type"] == "agent.fail" and e.get("agent")
    ]


def lifecycle_violations(events: list[Event]) -> list[str]:
    """Structural problems in the stream itself, independent of any case.

    The orchestrator's contract is that every delegation emits agent.start
    and exactly one terminal event. A violation means a step was dropped or
    double-counted, which would otherwise show up as a mysteriously good
    score rather than as a bug.
    """
    problems: list[str] = []

    starts = sum(1 for e in events if e["type"] == "agent.start")
    terminals = sum(1 for e in events if e["type"] in {"agent.complete", "agent.fail"})
    if starts != terminals:
        problems.append(
            f"{starts} agent.start vs {terminals} terminal events — "
            "a delegation was dropped or double-reported"
        )

    types = [e["type"] for e in events]
    if types and types[0] not in {"workflow.start", "workflow.cache_hit"}:
        problems.append(f"stream opens with {types[0]!r}, expected workflow.start")
    if types and types[-1] not in {"workflow.complete", "workflow.cache_hit"}:
        problems.append(f"stream ends with {types[-1]!r}, expected workflow.complete")

    # An agent must finish before the next one starts: delegation is
    # sequential, so interleaved lifecycles mean the stream is unreliable.
    open_agent: str | None = None
    for event in events:
        if event["type"] == "agent.start":
            if open_agent is not None:
                problems.append(
                    f"{event.get('agent')!r} started while {open_agent!r} was still open"
                )
            open_agent = event.get("agent")
        elif event["type"] in {"agent.complete", "agent.fail"}:
            open_agent = None

    return problems


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def trajectory_score(expected: list[str], actual: list[str]) -> float:
    """Position-by-position agreement, in 0..1.

    Dividing by the longer of the two penalises missing and extra steps
    alike. Scoring against len(expected) alone would give a run that does
    everything expected *plus* three unnecessary delegations a perfect mark.

    Two empty trajectories agree completely, so they score 1.0.
    """
    if not expected and not actual:
        return 1.0
    longest = max(len(expected), len(actual))
    matches = sum(1 for e, a in zip(expected, actual, strict=False) if e == a)
    return matches / longest


def _output_checks(case: EvalCase, output: str | None) -> list[Check]:
    checks: list[Check] = []
    haystack = (output or "").lower()

    for needle in case.expect.contains:
        checks.append(
            Check(
                name=f"contains:{needle}",
                passed=needle.lower() in haystack,
                detail=f"{needle!r} {'found' if needle.lower() in haystack else 'missing'}",
            )
        )
    for needle in case.expect.excludes:
        present = needle.lower() in haystack
        checks.append(
            Check(
                name=f"excludes:{needle}",
                passed=not present,
                detail=f"{needle!r} {'present' if present else 'absent'}",
            )
        )
    return checks


def score(
    case: EvalCase,
    state: WorkflowState,
    events: list[Event],
    duration_s: float = 0.0,
) -> CaseResult:
    """Grade one run against one case."""
    trajectory = agent_trajectory(events)
    checks: list[Check] = []

    expected = case.expect.agents
    if expected is not None:
        value = trajectory_score(expected, trajectory)
        threshold = case.expect.min_trajectory_score or 1.0
        checks.append(
            Check(
                name="trajectory",
                passed=value >= threshold,
                score=value,
                detail=f"expected {expected}, got {trajectory} (need {threshold:g})",
            )
        )

    for agent in case.expect.agents_include:
        checks.append(
            Check(
                name=f"includes:{agent}",
                passed=agent in trajectory,
                detail=(
                    f"{agent} {'ran' if agent in trajectory else 'never ran'}; "
                    f"trajectory was {trajectory}"
                ),
            )
        )

    if case.expect.succeeded is not None:
        checks.append(
            Check(
                name="succeeded",
                passed=state.succeeded == case.expect.succeeded,
                detail=(
                    f"expected succeeded={case.expect.succeeded}, "
                    f"got {state.succeeded}"
                    + (f" ({state.error})" if state.error else "")
                ),
            )
        )

    checks.extend(_output_checks(case, state.final_output))

    if case.expect.max_llm_calls is not None:
        calls = state.usage.calls
        checks.append(
            Check(
                name="max_llm_calls",
                passed=calls <= case.expect.max_llm_calls,
                detail=f"{calls} calls, ceiling {case.expect.max_llm_calls}",
            )
        )

    if case.expect.max_total_tokens is not None:
        tokens = state.usage.total_tokens
        checks.append(
            Check(
                name="max_total_tokens",
                passed=tokens <= case.expect.max_total_tokens,
                detail=f"{tokens} tokens, ceiling {case.expect.max_total_tokens}",
            )
        )

    if not case.expect.allow_step_failures:
        failed = failed_agents(events)
        checks.append(
            Check(
                name="no_step_failures",
                passed=not failed,
                detail=(
                    "; ".join(failure_reasons(events)) if failed else "no steps failed"
                ),
            )
        )

    # Always checked. A case cannot opt out of the orchestrator's own
    # contract, because a broken stream invalidates every score above.
    violations = lifecycle_violations(events)
    checks.append(
        Check(
            name="event_stream",
            passed=not violations,
            detail="; ".join(violations) if violations else "well-formed",
        )
    )

    return CaseResult(
        case_id=case.id,
        checks=checks,
        trajectory=trajectory,
        final_output=state.final_output,
        usage=state.usage,
        duration_s=duration_s,
    )
