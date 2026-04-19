"""Tests for CompareSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.compare import Comparison, CompareSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_compare_parses_llm_json():
    payload = {
        "items": ["FastAPI", "Flask"],
        "criteria": ["async", "ecosystem", "type hints"],
        "matrix": {
            "FastAPI": {"async": "native", "ecosystem": "growing", "type hints": "first-class"},
            "Flask": {"async": "via plugin", "ecosystem": "huge", "type hints": "manual"},
        },
        "recommendation": "FastAPI for new async APIs.",
        "reasoning": "Native async + Pydantic integration is hard to beat.",
    }
    subagent = CompareSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    report = await subagent.run(["FastAPI", "Flask"], context="building a REST API")

    assert isinstance(report, Comparison)
    assert "FastAPI" in report.matrix
    assert report.recommendation.startswith("FastAPI")


@pytest.mark.asyncio
async def test_compare_defaults_when_fields_missing():
    subagent = CompareSubagent(llm_client=make_mock_llm('{"recommendation": "either"}'))
    report = await subagent.run(["a", "b"])

    # We pre-populate items from the call args when the LLM omits them.
    assert report.items == ["a", "b"]
    assert report.criteria == []
    assert report.matrix == {}
    assert report.recommendation == "either"
    assert report.reasoning == ""
