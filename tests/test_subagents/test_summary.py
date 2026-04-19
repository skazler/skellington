"""Tests for SummarySubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.summary import Summary, SummarySubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_summary_parses_llm_json():
    payload = {
        "title": "Pydantic v2 overview",
        "key_points": ["fast", "type-safe", "json-schema"],
        "full_summary": "Pydantic v2 is a data validation library built on Rust core.",
        "word_count_original": 200,
        "word_count_summary": 12,
    }
    subagent = SummarySubagent(llm_client=make_mock_llm(json.dumps(payload)))
    report = await subagent.run("Pydantic v2 is the leading data validation library...")

    assert isinstance(report, Summary)
    assert report.title == "Pydantic v2 overview"
    assert "fast" in report.key_points
    assert report.word_count_summary == 12


@pytest.mark.asyncio
async def test_summary_defaults_when_fields_missing():
    # Only title given; everything else falls back to defaults.
    subagent = SummarySubagent(llm_client=make_mock_llm('{"title": "Brief"}'))
    content = "alpha bravo charlie delta echo"
    report = await subagent.run(content)

    assert report.title == "Brief"
    assert report.key_points == []
    assert report.full_summary == ""
    # Original word count is computed from the input, not trusted to the LLM.
    assert report.word_count_original == 5
    assert report.word_count_summary == 0


@pytest.mark.asyncio
async def test_summary_handles_fenced_json():
    payload = (
        '```json\n'
        '{"title": "Fenced", "key_points": ["a"], "full_summary": "ok",'
        ' "word_count_original": 3, "word_count_summary": 1}\n'
        '```'
    )
    subagent = SummarySubagent(llm_client=make_mock_llm(payload))
    report = await subagent.run("a b c")
    assert report.title == "Fenced"
    assert report.key_points == ["a"]
