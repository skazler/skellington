"""Tests for LintSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.lint import LintReport, LintSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_lint_parses_llm_json():
    payload = {
        "passed": False,
        "score": 0.6,
        "violations": [{"rule": "E501", "line": "12", "message": "line too long"}],
        "suggestions": ["break up long lines"],
    }
    subagent = LintSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    report = await subagent.run("print('x' * 200)")

    assert isinstance(report, LintReport)
    assert report.passed is False
    assert report.score == 0.6
    assert report.violations[0]["rule"] == "E501"
    assert report.suggestions == ["break up long lines"]


@pytest.mark.asyncio
async def test_lint_fills_defaults_for_minimal_output():
    # LLM returned only the mandatory pass/score — we default the rest.
    subagent = LintSubagent(llm_client=make_mock_llm('{"passed": true, "score": 0.95}'))
    report = await subagent.run("x = 1")

    assert report.passed is True
    assert report.score == 0.95
    assert report.violations == []
    assert report.suggestions == []


@pytest.mark.asyncio
async def test_lint_handles_fenced_json():
    payload = '```json\n{"passed": true, "score": 1.0, "violations": [], "suggestions": []}\n```'
    subagent = LintSubagent(llm_client=make_mock_llm(payload))
    report = await subagent.run("x = 1")
    assert report.passed is True
