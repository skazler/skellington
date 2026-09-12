"""
Running eval cases.

Learning goal: each case gets a fresh Orchestrator with a fresh set of
agents. That isolation is not politeness — it is the whole reason the global
AgentRegistry had to go. Cases that share agent instances share whatever the
previous case mutated, and the resulting scores measure the order you
happened to write the file in.

Determinism and accounting are both wired by decorating one client:
FixedTemperatureClient pins the temperature for every call in the run
(agents and their internally-constructed subagents alike), and
UsageTrackingClient records what each one cost.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

import structlog

from skellington.agents import default_agents
from skellington.core.llm import FixedTemperatureClient, LLMClient, LLMClientFactory
from skellington.core.orchestrator import Orchestrator
from skellington.core.types import Usage
from skellington.core.usage import UsageRecorder, UsageTrackingClient
from skellington.eval.trajectory import score
from skellington.eval.types import CaseResult, EvalCase, EvalReport, EvalSet

logger = structlog.get_logger(__name__)


AgentsFactory = Callable[[LLMClient], list[object]]
"""Builds a cast from an already-decorated client. The client must reach
every agent, or usage and temperature only apply to some of the run."""


def build_runtime(
    *,
    base_client: LLMClient | None = None,
    temperature: float = 0.0,
    agents_factory: AgentsFactory | None = None,
) -> tuple[list[object], UsageRecorder]:
    """Build one case's agents and the recorder watching them.

    Returns fresh agent instances every call. Reusing them across cases is
    the bug this design exists to prevent.

    `agents_factory` swaps the cast — for evaluating a subset, a modified
    specialist, or stubs. It receives the decorated client, so whatever it
    builds is still measured and still deterministic.
    """
    inner = base_client or LLMClientFactory.create()
    recorder = UsageRecorder()
    client = FixedTemperatureClient(UsageTrackingClient(inner, recorder), temperature)
    build = agents_factory or (lambda c: default_agents(llm_client=c))
    return build(client), recorder


async def run_case(
    case: EvalCase,
    *,
    base_client: LLMClient | None = None,
    temperature: float = 0.0,
    agents_factory: AgentsFactory | None = None,
) -> CaseResult:
    """Run one case and grade it.

    An exception during the run is reported as CaseResult.error rather than
    raised, so one broken case cannot take down the set — and so a harness
    bug reads differently from a failed assertion.
    """
    started = time.perf_counter()
    recorder: UsageRecorder | None = None
    events: list[dict] = []

    # Construction is inside the try because it can fail too — a missing API
    # key, a factory that blows up — and one bad case must not take the set
    # down with it.
    try:
        agents, recorder = build_runtime(
            base_client=base_client, temperature=temperature, agents_factory=agents_factory
        )
        orchestrator = Orchestrator(agents=agents, on_event=events.append, usage=recorder)
        state = await orchestrator.run(case.request)
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        logger.exception("eval case raised", case=case.id)
        return CaseResult(
            case_id=case.id,
            error=f"{type(exc).__name__}: {exc}",
            usage=recorder.snapshot() if recorder else Usage(),
            duration_s=time.perf_counter() - started,
        )

    return score(case, state, events, duration_s=time.perf_counter() - started)


async def run_set(
    eval_set: EvalSet,
    *,
    base_client: LLMClient | None = None,
    temperature: float = 0.0,
    agents_factory: AgentsFactory | None = None,
    only: Iterable[str] | None = None,
    on_result: object = None,
) -> EvalReport:
    """Run every case in a set, sequentially.

    Sequential on purpose: cases are independent, but running them in
    parallel multiplies the request rate against a shared API quota, and a
    rate-limit error would be scored as a case failure.

    `on_result` is called with each CaseResult as it lands, so a CLI can
    report progress without waiting for the whole set.
    """
    wanted = set(only) if only is not None else None
    cases = [c for c in eval_set.cases if wanted is None or c.id in wanted]

    if wanted is not None:
        missing = wanted - {c.id for c in eval_set.cases}
        if missing:
            raise KeyError(f"no such case(s) in {eval_set.name!r}: {sorted(missing)}")

    report = EvalReport(set_name=eval_set.name)
    for case in cases:
        result = await run_case(
            case,
            base_client=base_client,
            temperature=temperature,
            agents_factory=agents_factory,
        )
        report.results.append(result)
        if callable(on_result):
            on_result(result)
    return report
