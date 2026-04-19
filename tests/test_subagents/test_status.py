"""Tests for StatusSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.core.types import Task, TaskStatus, WorkflowState
from skellington.subagents.status import StatusReport, StatusSubagent
from tests.conftest import make_mock_llm


def _state_with(statuses: list[TaskStatus]) -> WorkflowState:
    state = WorkflowState(user_request="x")
    for i, s in enumerate(statuses):
        state.add_task(Task(title=f"task {i}", description="d", status=s))
    return state


@pytest.mark.asyncio
async def test_status_counts_come_from_state_not_llm():
    """Counts are deterministic; only narrative + next_steps come from the LLM."""
    state = _state_with(
        [
            TaskStatus.COMPLETE,
            TaskStatus.COMPLETE,
            TaskStatus.FAILED,
            TaskStatus.IN_PROGRESS,
        ]
    )
    payload = {"narrative": "Halfway done.", "next_steps": ["fix the failure"]}
    subagent = StatusSubagent(llm_client=make_mock_llm(json.dumps(payload)))

    report = await subagent.run(state)

    assert isinstance(report, StatusReport)
    assert report.total_tasks == 4
    assert report.completed == 2
    assert report.failed == 1
    assert report.in_progress == 1
    assert report.percentage_complete == 50.0
    assert report.narrative == "Halfway done."
    assert report.next_steps == ["fix the failure"]


@pytest.mark.asyncio
async def test_status_handles_empty_workflow_without_llm():
    """Empty workflow → no LLM call, sensible defaults."""
    state = WorkflowState(user_request="nothing yet")
    llm = make_mock_llm("should not be called")
    subagent = StatusSubagent(llm_client=llm)

    report = await subagent.run(state)

    assert report.total_tasks == 0
    assert report.percentage_complete == 0.0
    assert "No tasks" in report.narrative
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_status_defaults_when_llm_returns_minimal_json():
    state = _state_with([TaskStatus.COMPLETE])
    subagent = StatusSubagent(llm_client=make_mock_llm("{}"))

    report = await subagent.run(state)

    assert report.completed == 1
    assert report.percentage_complete == 100.0
    assert report.narrative == "Workflow in progress."
    assert report.next_steps == []
