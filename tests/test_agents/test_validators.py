"""Integration tests for Lock, Shock, Barrel and the ValidatorCoordinator (Phase 6)."""

from __future__ import annotations

import json

import pytest

from skellington.agents.validators import Barrel, Lock, Shock, ValidatorCoordinator
from skellington.core.types import AgentName, Task, ValidationVerdict, WorkflowState
from tests.conftest import make_mock_llm


# ---------------------------------------------------------------------------
# Individual validator agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_produces_verdict_from_lint_report():
    payload = {
        "passed": True,
        "score": 0.9,
        "violations": [{"rule": "E501", "line": "3", "message": "line too long"}],
        "suggestions": ["wrap at 88"],
    }
    lock = Lock(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(title="review", description="code", context={"code": "def f(): pass"})
    state = WorkflowState(user_request="review")

    response = await lock.run(task, state)

    assert response.agent == AgentName.LOCK
    verdict = ValidationVerdict.model_validate(response.metadata["verdict"])
    assert verdict.passed is True
    assert verdict.score == 0.9
    assert "line too long" in verdict.issues


@pytest.mark.asyncio
async def test_shock_produces_verdict_from_test_report():
    payload = {
        "passed": False,
        "score": 0.5,
        "suggested_tests": ["test_empty"],
        "coverage_estimate": 0.25,
        "missing_test_cases": ["empty input", "unicode"],
    }
    shock = Shock(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(title="review", description="code", context={"code": "def f(): pass"})
    response = await shock.run(task, WorkflowState(user_request="x"))

    verdict = ValidationVerdict.model_validate(response.metadata["verdict"])
    assert verdict.validator == AgentName.SHOCK
    assert verdict.passed is False
    assert "empty input" in verdict.issues


@pytest.mark.asyncio
async def test_barrel_produces_verdict_from_security_report():
    payload = {
        "passed": False,
        "score": 0.3,
        "vulnerabilities": [
            {"severity": "high", "type": "sql_injection", "description": "unsafe f-string"}
        ],
        "recommendations": ["use params"],
    }
    barrel = Barrel(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="review",
        description="code",
        context={"code": "cursor.execute(f'SELECT {x}')"},
    )
    response = await barrel.run(task, WorkflowState(user_request="x"))

    verdict = ValidationVerdict.model_validate(response.metadata["verdict"])
    assert verdict.validator == AgentName.BARREL
    assert verdict.passed is False
    assert "unsafe f-string" in verdict.issues


@pytest.mark.asyncio
async def test_validator_falls_back_to_task_description_without_code_context():
    """No task.context['code'] → the validator still reviews task.description."""
    payload = {"passed": True, "score": 0.8}
    lock = Lock(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(title="review", description="print('hi')")
    response = await lock.run(task, WorkflowState(user_request="x"))

    verdict = ValidationVerdict.model_validate(response.metadata["verdict"])
    assert verdict.passed is True


# ---------------------------------------------------------------------------
# ValidatorCoordinator — consensus
# ---------------------------------------------------------------------------


def _pass() -> str:
    return json.dumps({"passed": True, "score": 0.9})


def _fail() -> str:
    return json.dumps({"passed": False, "score": 0.2})


@pytest.mark.asyncio
async def test_consensus_passes_with_majority():
    # 2 pass, 1 fail → majority passes
    coordinator = ValidatorCoordinator(
        lock=Lock(llm_client=make_mock_llm(_pass())),
        shock=Shock(llm_client=make_mock_llm(_pass())),
        barrel=Barrel(llm_client=make_mock_llm(_fail())),
    )
    task = Task(title="review", description="x = 1")
    state = WorkflowState(user_request="review")

    consensus = await coordinator.validate("x = 1", task, state)

    assert consensus.passed is True
    assert sum(1 for v in consensus.verdicts if v.passed) == 2
    assert 0.0 < consensus.average_score < 1.0
    # Consensus is published on workflow state so downstream agents can read it.
    assert str(task.id) in state.metadata["validation"]


@pytest.mark.asyncio
async def test_consensus_fails_with_majority():
    coordinator = ValidatorCoordinator(
        lock=Lock(llm_client=make_mock_llm(_fail())),
        shock=Shock(llm_client=make_mock_llm(_fail())),
        barrel=Barrel(llm_client=make_mock_llm(_pass())),
    )
    task = Task(title="review", description="x = 1")
    consensus = await coordinator.validate(
        "x = 1", task, WorkflowState(user_request="review")
    )

    assert consensus.passed is False
    assert sum(1 for v in consensus.verdicts if not v.passed) == 2


@pytest.mark.asyncio
async def test_consensus_survives_a_failing_validator():
    """If one validator explodes, the others still vote — no single point of failure."""

    class BrokenLock(Lock):
        async def run(self, task, state):  # type: ignore[override]
            raise RuntimeError("boom")

    coordinator = ValidatorCoordinator(
        lock=BrokenLock(llm_client=make_mock_llm("ignored")),
        shock=Shock(llm_client=make_mock_llm(_pass())),
        barrel=Barrel(llm_client=make_mock_llm(_pass())),
    )
    task = Task(title="review", description="x = 1")
    consensus = await coordinator.validate(
        "x = 1", task, WorkflowState(user_request="review")
    )

    # 2 pass (Shock, Barrel), 1 synthetic failure (Lock) → majority still passes.
    assert consensus.passed is True
    lock_verdict = next(v for v in consensus.verdicts if v.validator == AgentName.LOCK)
    assert lock_verdict.passed is False
    assert "boom" in lock_verdict.feedback
