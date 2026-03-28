"""Tests for core types and data models."""

from uuid import UUID

import pytest

from skellington.core.types import (
    AgentName,
    ConsensusResult,
    Task,
    TaskStatus,
    ValidationVerdict,
    WorkflowState,
)


def test_task_defaults():
    task = Task(title="Test task", description="Do something")
    assert task.status == TaskStatus.PENDING
    assert isinstance(task.id, UUID)


def test_workflow_state_add_task():
    state = WorkflowState(user_request="hello")
    task = Task(title="t1", description="d1")
    state.add_task(task)
    assert len(state.tasks) == 1
    assert state.get_task(task.id) is task


def test_consensus_majority_pass():
    verdicts = [
        ValidationVerdict(validator=AgentName.LOCK, passed=True, score=0.9, feedback="good"),
        ValidationVerdict(validator=AgentName.SHOCK, passed=True, score=0.8, feedback="ok"),
        ValidationVerdict(validator=AgentName.BARREL, passed=False, score=0.4, feedback="issue"),
    ]
    result = ConsensusResult.from_verdicts(verdicts)
    assert result.passed is True
    assert result.average_score == pytest.approx((0.9 + 0.8 + 0.4) / 3)


def test_consensus_majority_fail():
    verdicts = [
        ValidationVerdict(validator=AgentName.LOCK, passed=False, score=0.3, feedback="bad"),
        ValidationVerdict(validator=AgentName.SHOCK, passed=False, score=0.4, feedback="bad"),
        ValidationVerdict(validator=AgentName.BARREL, passed=True, score=0.9, feedback="fine"),
    ]
    result = ConsensusResult.from_verdicts(verdicts)
    assert result.passed is False
