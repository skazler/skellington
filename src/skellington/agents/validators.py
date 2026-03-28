"""
👹🧝 Lock, Shock & Barrel — The Validators

The trick-or-treat trio who've become Christmas code review elves.
They never agree on everything — and that's the point.

Role: VALIDATORS (multi-agent consensus)
- Each validator independently reviews code
- They vote: passed / failed
- Majority rules (2/3 = pass)
- Divergent opinions surface more issues

Key pattern: MULTI-AGENT CONSENSUS via parallel subagents

Subagents: LintSubagent, TestSubagent, SecuritySubagent
MCP Servers: code_exec
"""

from __future__ import annotations

import structlog

from skellington.core.agent import BaseAgent
from skellington.core.subagent import run_subagents_parallel
from skellington.core.types import (
    AgentName,
    AgentResponse,
    ConsensusResult,
    Message,
    MessageRole,
    Task,
    ValidationVerdict,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


class Lock(BaseAgent):
    """Lock — the ringleader validator. Focuses on correctness and logic."""

    name = AgentName.LOCK
    emoji = "👹"
    description = "Validator: logic correctness, functional review"

    @property
    def system_prompt(self) -> str:
        return """You are Lock — the scheming ringleader of the trick-or-treat trio,
now running logic review for Christmas code.

You review code for:
- Logical correctness: does it do what it claims?
- Edge cases and error handling
- Algorithm efficiency
- Functional completeness

Be critical but constructive. Score from 0.0 to 1.0. Provide specific, actionable feedback.
Output a JSON object: {"passed": bool, "score": float, "feedback": str, "issues": [str]}"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Review this code for logic correctness:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)


class Shock(BaseAgent):
    """Shock — the clever one. Focuses on style and maintainability."""

    name = AgentName.SHOCK
    emoji = "🔮👹"
    description = "Validator: code style, maintainability, documentation"

    @property
    def system_prompt(self) -> str:
        return """You are Shock — the most clever of the trick-or-treat trio, wearing your witch hat
and reviewing code style for Christmas quality.

You review code for:
- Code style and readability (PEP 8, naming, structure)
- Documentation quality (docstrings, comments, type hints)
- Maintainability (complexity, coupling, cohesion)
- Test coverage and test quality

Be critical but constructive. Score from 0.0 to 1.0. Provide specific, actionable feedback.
Output a JSON object: {"passed": bool, "score": float, "feedback": str, "issues": [str]}"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Review this code for style and maintainability:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)


class Barrel(BaseAgent):
    """Barrel — the wild one. Focuses on security and robustness."""

    name = AgentName.BARREL
    emoji = "💀👹"
    description = "Validator: security, robustness, vulnerability scanning"

    @property
    def system_prompt(self) -> str:
        return """You are Barrel — the wild, round one of the trick-or-treat trio, rolling into
Christmas security reviews with chaotic energy.

You review code for:
- Security vulnerabilities (injection, auth, data exposure)
- Input validation and sanitization
- Dependency vulnerabilities
- Resource management (memory leaks, file handles, connections)
- Robustness under adversarial conditions

Be critical but constructive. Score from 0.0 to 1.0. Provide specific, actionable feedback.
Output a JSON object: {"passed": bool, "score": float, "feedback": str, "issues": [str]}"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Review this code for security and robustness:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)


# ---------------------------------------------------------------------------
# The combined validator coordinator
# ---------------------------------------------------------------------------


class ValidatorCoordinator:
    """
    Coordinates Lock, Shock & Barrel to produce a consensus verdict.

    This is the multi-agent consensus pattern in action:
    - All three run IN PARALLEL (see run_subagents_parallel)
    - Each produces an independent verdict
    - ConsensusResult.from_verdicts() applies majority voting
    """

    def __init__(self) -> None:
        self.lock = Lock()
        self.shock = Shock()
        self.barrel = Barrel()
        self.log = logger.bind(component="validator_coordinator")

    async def validate(self, code: str, task: Task, state: WorkflowState) -> ConsensusResult:
        """Run all three validators in parallel and return the consensus."""
        self.log.info("running parallel validation")

        code_task = Task(
            title="Validate code",
            description=code,
            parent_task_id=task.id,
        )

        # Run all three in parallel — this is the performance win of parallel subagents
        results = await run_subagents_parallel(
            [
                (self.lock, (code_task, state), {}),
                (self.shock, (code_task, state), {}),
                (self.barrel, (code_task, state), {}),
            ]
        )

        import json

        verdicts = []
        for agent, result in zip([AgentName.LOCK, AgentName.SHOCK, AgentName.BARREL], results):
            if isinstance(result, Exception):
                self.log.error("validator failed", agent=agent.value, error=str(result))
                verdicts.append(
                    ValidationVerdict(
                        validator=agent,
                        passed=False,
                        score=0.0,
                        feedback=f"Validator failed: {result}",
                    )
                )
            else:
                try:
                    data = json.loads(result.content)
                    verdicts.append(
                        ValidationVerdict(
                            validator=agent,
                            passed=data.get("passed", False),
                            score=float(data.get("score", 0.0)),
                            feedback=data.get("feedback", ""),
                            issues=data.get("issues", []),
                        )
                    )
                except (json.JSONDecodeError, KeyError):
                    verdicts.append(
                        ValidationVerdict(
                            validator=agent,
                            passed=True,
                            score=0.7,
                            feedback=result.content,
                        )
                    )

        return ConsensusResult.from_verdicts(verdicts)
