"""
👹🧝 Lock, Shock & Barrel — The Validators

"Kidnap the Sandy Claws... then ship him to code review."

The trick-or-treat trio, now the consensus-based Christmas review board.
Each reviews code through their own specialist lens, then the coordinator
combines their verdicts by majority vote.

Role: VALIDATORS (multi-agent consensus)
- Each validator delegates to its specialist subagent (Lint / Test / Security)
- Each produces a ValidationVerdict (passed, score, feedback, issues)
- ValidatorCoordinator runs all three IN PARALLEL and applies majority rules

Key pattern: multi-agent consensus via parallel subagents. Lock, Shock and
Barrel are intentionally thin — all the domain work lives in their subagents.
Keeping the agent layer thin is what makes swapping a reviewer (e.g. Lock
gets a new LintSubagent implementation) a one-line change.
"""

from __future__ import annotations

from typing import Any

import structlog

from skellington.core.agent import BaseAgent
from skellington.core.llm import LLMClient
from skellington.core.subagent import run_subagents_parallel
from skellington.core.types import (
    AgentName,
    AgentResponse,
    ConsensusResult,
    LLMProvider,
    Task,
    ValidationVerdict,
    WorkflowState,
)
from skellington.subagents.lint import LintReport, LintSubagent
from skellington.subagents.security import SecurityReport, SecuritySubagent
from skellington.subagents.test_runner import TestReport, TestSubagent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_code(task: Task) -> str:
    """Pull the code under review out of task context, falling back to description."""
    ctx = task.context or {}
    for key in ("code", "source", "source_code"):
        if key in ctx and isinstance(ctx[key], str):
            return ctx[key]
    return task.description


def _verdict_response(
    name: AgentName, task: Task, verdict: ValidationVerdict, extra: dict[str, Any]
) -> AgentResponse:
    """Wrap a ValidationVerdict in a standard AgentResponse."""
    return AgentResponse(
        agent=name,
        task_id=task.id,
        content=verdict.feedback or f"{name.value}: {'passed' if verdict.passed else 'failed'}",
        success=True,
        metadata={"verdict": verdict.model_dump(mode="json"), **extra},
    )


# ---------------------------------------------------------------------------
# Lock — logic / style (via LintSubagent)
# ---------------------------------------------------------------------------


class Lock(BaseAgent):
    """Lock — the scheming ringleader. Owns static analysis via LintSubagent."""

    name = AgentName.LOCK
    emoji = "👹"
    description = "Validator: logic correctness, static analysis (via LintSubagent)"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)

    @property
    def system_prompt(self) -> str:
        return """You are Lock — the scheming ringleader of the trick-or-treat trio,
running logic review for Christmas code. You delegate the grunt work to
LintSubagent and translate its findings into a final verdict."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        code = _extract_code(task)
        report: LintReport = await LintSubagent(llm_client=self._llm).run(code)

        issues = [
            v.get("message") or v.get("rule") or str(v)
            for v in report.violations
            if isinstance(v, dict)
        ]
        feedback = (
            f"Lint: {len(report.violations)} violations, "
            f"{len(report.suggestions)} suggestions."
        )
        verdict = ValidationVerdict(
            validator=AgentName.LOCK,
            passed=report.passed,
            score=report.score,
            feedback=feedback,
            issues=issues,
        )
        return _verdict_response(self.name, task, verdict, {"report": report.model_dump()})


# ---------------------------------------------------------------------------
# Shock — testability / coverage (via TestSubagent)
# ---------------------------------------------------------------------------


class Shock(BaseAgent):
    """Shock — the clever one. Owns test coverage via TestSubagent."""

    name = AgentName.SHOCK
    emoji = "🔮👹"
    description = "Validator: testability & coverage (via TestSubagent)"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)

    @property
    def system_prompt(self) -> str:
        return """You are Shock — the clever witch-hatted member of the trio, reviewing
code through the lens of testability. You delegate to TestSubagent and
translate its coverage report into a verdict."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        code = _extract_code(task)
        report: TestReport = await TestSubagent(llm_client=self._llm).run(code)

        feedback = (
            f"Test coverage ~{report.coverage_estimate:.0%}; "
            f"{len(report.suggested_tests)} tests suggested, "
            f"{len(report.missing_test_cases)} gaps."
        )
        verdict = ValidationVerdict(
            validator=AgentName.SHOCK,
            passed=report.passed,
            score=report.score,
            feedback=feedback,
            issues=report.missing_test_cases,
        )
        return _verdict_response(self.name, task, verdict, {"report": report.model_dump()})


# ---------------------------------------------------------------------------
# Barrel — security (via SecuritySubagent)
# ---------------------------------------------------------------------------


class Barrel(BaseAgent):
    """Barrel — the wild, round one. Owns security review via SecuritySubagent."""

    name = AgentName.BARREL
    emoji = "💀👹"
    description = "Validator: security & robustness (via SecuritySubagent)"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)

    @property
    def system_prompt(self) -> str:
        return """You are Barrel — the wild, round one of the trio, rolling through
security reviews with chaotic energy. You delegate to SecuritySubagent and
translate its vulnerability report into a verdict."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        code = _extract_code(task)
        report: SecurityReport = await SecuritySubagent(llm_client=self._llm).run(code)

        issues = [
            v.get("description") or v.get("type") or str(v)
            for v in report.vulnerabilities
            if isinstance(v, dict)
        ]
        feedback = (
            f"Security: {len(report.vulnerabilities)} vulnerabilities, "
            f"{len(report.recommendations)} recommendations."
        )
        verdict = ValidationVerdict(
            validator=AgentName.BARREL,
            passed=report.passed,
            score=report.score,
            feedback=feedback,
            issues=issues,
        )
        return _verdict_response(self.name, task, verdict, {"report": report.model_dump()})


# ---------------------------------------------------------------------------
# ValidatorCoordinator — the consensus engine
# ---------------------------------------------------------------------------


class ValidatorCoordinator:
    """
    Coordinates Lock, Shock & Barrel to produce a consensus verdict.

    Multi-agent consensus pattern in action:
    - All three validators run IN PARALLEL (asyncio.gather under the hood)
    - Each produces an independent ValidationVerdict
    - ConsensusResult.from_verdicts() applies majority voting (2/3 = pass)
    - A single validator raising an exception becomes a failed verdict — no
      reviewer can bring the whole panel down
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        lock: Lock | None = None,
        shock: Shock | None = None,
        barrel: Barrel | None = None,
    ) -> None:
        self.lock = lock or Lock(llm_client=llm_client, provider=provider)
        self.shock = shock or Shock(llm_client=llm_client, provider=provider)
        self.barrel = barrel or Barrel(llm_client=llm_client, provider=provider)
        self.log = logger.bind(component="validator_coordinator")

    async def validate(self, code: str, task: Task, state: WorkflowState) -> ConsensusResult:
        """Run all three validators in parallel and return the consensus."""
        self.log.info("running parallel validation", task=task.title)

        code_task = Task(
            title="Validate code",
            description=code,
            parent_task_id=task.id,
            context={"code": code},
        )

        # Parallel execution — this is the win: 1x latency instead of 3x.
        results = await run_subagents_parallel(
            [
                (self.lock, (code_task, state), {}),
                (self.shock, (code_task, state), {}),
                (self.barrel, (code_task, state), {}),
            ]
        )

        order = (AgentName.LOCK, AgentName.SHOCK, AgentName.BARREL)
        verdicts: list[ValidationVerdict] = []
        for agent_name, result in zip(order, results):
            if isinstance(result, Exception):
                self.log.error("validator failed", agent=agent_name.value, error=str(result))
                verdicts.append(
                    ValidationVerdict(
                        validator=agent_name,
                        passed=False,
                        score=0.0,
                        feedback=f"Validator failed: {result}",
                    )
                )
                continue

            verdicts.append(_verdict_from_response(agent_name, result))

        consensus = ConsensusResult.from_verdicts(verdicts)
        state.metadata.setdefault("validation", {})[str(task.id)] = consensus.model_dump(mode="json")
        return consensus


def _verdict_from_response(agent_name: AgentName, response: AgentResponse) -> ValidationVerdict:
    """Pull the ValidationVerdict out of an AgentResponse, with a safe fallback."""
    raw = (response.metadata or {}).get("verdict")
    if isinstance(raw, dict):
        try:
            return ValidationVerdict.model_validate(raw)
        except Exception:  # noqa: BLE001 — fall through to heuristic below
            pass
    return ValidationVerdict(
        validator=agent_name,
        passed=response.success,
        score=0.5 if response.success else 0.0,
        feedback=response.content or "",
    )
