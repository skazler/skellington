"""Integration tests for Oogie.run() — Phase 5 (research + compare)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.agents.oogie import Oogie
from skellington.core.types import AgentName, LLMProvider, Task, WorkflowState


def _toolkit(results):
    """Build a fake search toolkit whose `web_search` returns `results`."""
    toolkit = MagicMock()
    toolkit.web_search = AsyncMock(return_value=results)
    return toolkit


def _scripted_llm(responses: list[str]):
    """An LLM mock that returns each scripted response in order, then repeats the last."""
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


_SUMMARY_JSON = json.dumps(
    {
        "title": "Pydantic v2",
        "key_points": ["fast", "type-safe"],
        "full_summary": "Pydantic v2 is a data validation library.",
        "word_count_original": 100,
        "word_count_summary": 7,
    }
)

_COMPARE_JSON = json.dumps(
    {
        "items": ["FastAPI", "Flask"],
        "criteria": ["async", "ecosystem"],
        "matrix": {
            "FastAPI": {"async": "native", "ecosystem": "growing"},
            "Flask": {"async": "via plugin", "ecosystem": "huge"},
        },
        "recommendation": "FastAPI for new APIs.",
        "reasoning": "Async + Pydantic baked in.",
    }
)


@pytest.mark.asyncio
async def test_oogie_researches_with_real_toolkit_results():
    """Search via toolkit (no LLM call) → 3 summaries → synthesis report."""
    hits = [
        {"title": "Brave docs", "url": "https://brave.com/docs", "snippet": "search api"},
        {"title": "Tavily docs", "url": "https://tavily.com", "snippet": "research api"},
        {"title": "DuckDuckGo", "url": "https://duckduckgo.com", "snippet": "private search"},
    ]
    # Three summary calls + one synthesis call.
    llm = _scripted_llm([_SUMMARY_JSON, _SUMMARY_JSON, _SUMMARY_JSON, "Oogie's report."])
    oogie = Oogie(llm_client=llm, search=_toolkit(hits))

    task = Task(title="research", description="best web search APIs for python")
    state = WorkflowState(user_request=task.description)

    response = await oogie.run(task, state)

    assert response.agent == AgentName.OOGIE
    assert response.success is True
    assert response.metadata["intent"] == "research"
    assert response.metadata["source_count"] == 3
    assert response.metadata["summary_count"] == 3
    assert response.metadata["compared"] is False
    assert response.content == "Oogie's report."

    research = state.metadata["research"][str(task.id)]
    assert research["intent"] == "research"
    assert research["result_count"] == 3
    assert len(research["summaries"]) == 3
    assert research["comparison"] is None


@pytest.mark.asyncio
async def test_oogie_falls_back_to_llm_when_toolkit_raises():
    """Toolkit failure (e.g. no Brave/Tavily key) → SearchSubagent uses the LLM."""
    broken = MagicMock()
    broken.web_search = AsyncMock(side_effect=RuntimeError("no API key"))

    search_payload = json.dumps(
        {
            "query": "structlog",
            "results": [
                {"title": "structlog", "url": "https://www.structlog.org", "snippet": "logs"},
            ],
            "total_found": 1,
        }
    )
    # 1 search (LLM fallback) + 1 summary + 1 synthesis.
    llm = _scripted_llm([search_payload, _SUMMARY_JSON, "Report."])
    oogie = Oogie(llm_client=llm, search=broken)

    task = Task(title="research", description="what is structlog")
    state = WorkflowState(user_request=task.description)

    response = await oogie.run(task, state)

    assert response.metadata["source_count"] == 1
    assert response.metadata["summary_count"] == 1
    assert response.content == "Report."


@pytest.mark.asyncio
async def test_oogie_runs_compare_when_intent_detected():
    """`Compare X vs Y` → search + summaries + comparison."""
    hits = [
        {"title": "FastAPI", "url": "https://fastapi.tiangolo.com", "snippet": "modern API"},
        {"title": "Flask", "url": "https://flask.palletsprojects.com", "snippet": "micro framework"},
    ]
    # 2 summaries + 1 compare + 1 synthesis.
    llm = _scripted_llm([_SUMMARY_JSON, _SUMMARY_JSON, _COMPARE_JSON, "Verdict: FastAPI."])
    oogie = Oogie(llm_client=llm, search=_toolkit(hits))

    task = Task(
        title="comparison",
        description="Compare FastAPI vs Flask for a new API",
        context={"items": ["FastAPI", "Flask"], "max_summaries": 2},
    )
    state = WorkflowState(user_request=task.description)

    response = await oogie.run(task, state)

    assert response.metadata["intent"] == "compare"
    assert response.metadata["compared"] is True
    research = state.metadata["research"][str(task.id)]
    assert research["comparison"]["recommendation"].startswith("FastAPI")


@pytest.mark.asyncio
async def test_oogie_skips_compare_without_enough_items():
    """Compare intent but only one item → fall back to plain research."""
    hits = [{"title": "FastAPI", "url": "https://fastapi.tiangolo.com", "snippet": "API"}]
    llm = _scripted_llm([_SUMMARY_JSON, "Just one source."])
    oogie = Oogie(llm_client=llm, search=_toolkit(hits))

    # "compare FastAPI" — no second item, no 'vs' separator.
    task = Task(title="comparison", description="compare FastAPI", context={"max_summaries": 1})
    state = WorkflowState(user_request=task.description)

    response = await oogie.run(task, state)

    assert response.metadata["intent"] == "compare"
    # Compare was attempted but skipped: only 1 item available.
    assert response.metadata["compared"] is False


@pytest.mark.asyncio
async def test_oogie_publishes_research_to_state_metadata():
    """Downstream agents (Mayor) read research findings off state.metadata."""
    hits = [{"title": "Doc", "url": "https://example.com", "snippet": "snippet"}]
    llm = _scripted_llm([_SUMMARY_JSON, "Report."])
    oogie = Oogie(llm_client=llm, search=_toolkit(hits))

    task = Task(title="research", description="anything", context={"max_summaries": 1})
    state = WorkflowState(user_request=task.description)
    await oogie.run(task, state)

    assert "research" in state.metadata
    research = state.metadata["research"][str(task.id)]
    assert research["query"] == "anything"
    assert research["sources"] == hits
