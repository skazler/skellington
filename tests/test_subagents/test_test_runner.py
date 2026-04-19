"""Tests for TestSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.test_runner import TestReport, TestSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_test_runner_parses_llm_json():
    payload = {
        "passed": True,
        "score": 0.85,
        "suggested_tests": ["test_count_empty_string", "test_count_unicode"],
        "coverage_estimate": 0.7,
        "missing_test_cases": ["empty input", "unicode whitespace"],
    }
    subagent = TestSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    report = await subagent.run("def count(t): return len(t.split())")

    assert isinstance(report, TestReport)
    assert report.coverage_estimate == 0.7
    assert len(report.suggested_tests) == 2
    assert "empty input" in report.missing_test_cases


@pytest.mark.asyncio
async def test_test_runner_defaults_when_fields_missing():
    subagent = TestSubagent(llm_client=make_mock_llm('{"passed": false, "score": 0.3}'))
    report = await subagent.run("def f(): pass")

    assert report.passed is False
    assert report.score == 0.3
    assert report.suggested_tests == []
    assert report.coverage_estimate == 0.0
    assert report.missing_test_cases == []
