"""Tests for SearchSubagent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.subagents.search import SearchResult, SearchSubagent
from tests.conftest import make_mock_llm


def _toolkit(results):
    """Build a fake search toolkit whose `web_search` returns `results`."""
    toolkit = MagicMock()
    toolkit.web_search = AsyncMock(return_value=results)
    return toolkit


@pytest.mark.asyncio
async def test_search_uses_toolkit_when_present():
    hits = [
        {"title": "Pydantic v2", "url": "https://docs.pydantic.dev", "snippet": "data validation"},
        {"title": "FastAPI", "url": "https://fastapi.tiangolo.com", "snippet": "modern web API"},
    ]
    llm = make_mock_llm("should not be called")
    subagent = SearchSubagent(llm_client=llm, search=_toolkit(hits))

    report = await subagent.run("python web framework", num_results=2)

    assert isinstance(report, SearchResult)
    assert report.total_found == 2
    assert report.results == hits
    assert report.query == "python web framework"
    # Toolkit hit means we never went to the LLM.
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_search_falls_back_to_llm_without_toolkit():
    payload = {
        "query": "what is structlog",
        "results": [{"title": "structlog", "url": "https://www.structlog.org", "snippet": "logs"}],
        "total_found": 1,
    }
    subagent = SearchSubagent(llm_client=make_mock_llm(json.dumps(payload)))

    report = await subagent.run("what is structlog")

    assert report.total_found == 1
    assert report.results[0]["title"] == "structlog"


@pytest.mark.asyncio
async def test_search_falls_back_when_toolkit_raises():
    """Toolkit failure (e.g. no API key) → SearchSubagent uses the LLM instead."""
    broken = MagicMock()
    broken.web_search = AsyncMock(side_effect=RuntimeError("no API key"))

    payload = {"query": "x", "results": [], "total_found": 0}
    subagent = SearchSubagent(
        llm_client=make_mock_llm(json.dumps(payload)),
        search=broken,
    )

    report = await subagent.run("x")
    assert report.total_found == 0
    assert report.results == []


@pytest.mark.asyncio
async def test_search_defaults_query_when_llm_omits_it():
    # LLM returns minimal JSON — we patch in the original query.
    subagent = SearchSubagent(llm_client=make_mock_llm('{"results": []}'))
    report = await subagent.run("oogie's gambling odds")
    assert report.query == "oogie's gambling odds"
    assert report.total_found == 0
