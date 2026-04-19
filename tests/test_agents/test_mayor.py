"""Integration tests for Mayor.run() — Phase 8."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.agents.mayor import Mayor
from skellington.core.types import (
    AgentName,
    LLMProvider,
    Task,
    TaskStatus,
    WorkflowState,
)


def _scripted_llm(responses: list[str]):
    """LLM mock that returns each scripted response in order, then repeats the last."""
    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC

    iterator = iter(responses)
    last = responses[-1]

    async def complete(*_args, **_kwargs):
        nonlocal last
        try:
            content = next(iterator)
            last = content
        except StopIteration:
            content = last
        return MagicMock(
            content=content,
            tool_calls=[],
            model="test",
            input_tokens=5,
            output_tokens=5,
        )

    llm.complete = AsyncMock(side_effect=complete)
    return llm


_STATUS_JSON = json.dumps({"narrative": "Most tasks complete.", "next_steps": ["ship it"]})
_FORMAT_JSON = json.dumps(
    {"format": "markdown", "content": "# Final Report\n\nAll good.", "title": "Skellington Report"}
)
_DIFF_JSON = json.dumps({"change_summary": "added type hints"})


@pytest.mark.asyncio
async def test_mayor_produces_report_from_state_metadata():
    """Mayor reads navigation/builds/research/validation off state.metadata."""
    state = WorkflowState(user_request="build me a thing")
    state.add_task(Task(title="t1", description="d", status=TaskStatus.COMPLETE))
    state.add_task(Task(title="t2", description="d", status=TaskStatus.COMPLETE))
    state.metadata = {
        "navigation": {"./": {"relevant_files": ["a.py", "b.py"]}},
        "builds": {"abc": {"intent": "codegen", "files_written": ["/tmp/out.py"]}},
        "research": {
            "xyz": {
                "query": "how to test asyncio",
                "result_count": 3,
                "summaries": [{}, {}],
                "comparison": None,
            }
        },
        "validation": {
            "vvv": {
                "passed": True,
                "average_score": 0.91,
                "summary": "3/3 validators passed",
            }
        },
    }

    # Status (1) + Format (1) + Mayor synthesis chat (1) = 3 LLM calls.
    llm = _scripted_llm([_STATUS_JSON, _FORMAT_JSON, "Megaphone announcement!"])
    mayor = Mayor(llm_client=llm)

    task = Task(title="report", description="summarize the workflow")
    response = await mayor.run(task, state)

    assert response.agent == AgentName.MAYOR
    assert response.success is True
    assert response.metadata["completed"] == 2
    assert response.metadata["total_tasks"] == 2
    assert response.metadata["percentage_complete"] == 100.0
    assert response.metadata["format"] == "markdown"
    assert response.metadata["report"].startswith("# Final Report")
    assert response.metadata["diffed"] is False
    assert response.content == "Megaphone announcement!"

    # Mayor publishes its own report digest for inspection / re-rendering.
    report = state.metadata["reports"][str(task.id)]
    assert report["format"] == "markdown"
    assert report["status"]["completed"] == 2


@pytest.mark.asyncio
async def test_mayor_runs_diff_when_before_and_after_are_provided():
    state = WorkflowState(user_request="refactor")
    state.add_task(Task(title="t1", description="d", status=TaskStatus.COMPLETE))

    # Status + Diff + Format + synthesis = 4 calls.
    llm = _scripted_llm([_STATUS_JSON, _DIFF_JSON, _FORMAT_JSON, "Done."])
    mayor = Mayor(llm_client=llm)

    task = Task(
        title="report",
        description="report on the refactor",
        context={
            "before": "def f(): pass\n",
            "after": "def f() -> None:\n    pass\n",
            "filename": "x.py",
            "format": "markdown",
        },
    )

    response = await mayor.run(task, state)

    assert response.metadata["diffed"] is True
    report = state.metadata["reports"][str(task.id)]
    assert report["diff"] is not None
    assert report["diff"]["files_changed"] == ["x.py"]
    assert report["diff"]["change_summary"] == "added type hints"


@pytest.mark.asyncio
async def test_mayor_works_with_empty_workflow():
    """Empty state → status short-circuits (no LLM call), format + synthesis still run."""
    state = WorkflowState(user_request="nothing yet")
    # Status sub skips LLM (empty); Format + synthesis = 2 calls.
    llm = _scripted_llm([_FORMAT_JSON, "Nothing to report yet."])
    mayor = Mayor(llm_client=llm)

    task = Task(title="report", description="status please")
    response = await mayor.run(task, state)

    assert response.metadata["total_tasks"] == 0
    assert response.metadata["percentage_complete"] == 0.0
    assert response.success is True


@pytest.mark.asyncio
async def test_mayor_respects_requested_format():
    state = WorkflowState(user_request="x")
    state.add_task(Task(title="t1", description="d", status=TaskStatus.COMPLETE))

    html_format = json.dumps(
        {"format": "html", "content": "<h1>Report</h1>", "title": "Web View"}
    )
    llm = _scripted_llm([_STATUS_JSON, html_format, "Done."])
    mayor = Mayor(llm_client=llm)

    task = Task(title="report", description="d", context={"format": "html", "title": "Web View"})
    response = await mayor.run(task, state)

    assert response.metadata["format"] == "html"
    assert response.metadata["title"] == "Web View"
    assert "<h1>" in response.metadata["report"]
