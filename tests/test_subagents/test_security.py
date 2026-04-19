"""Tests for SecuritySubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.security import SecurityReport, SecuritySubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_security_parses_llm_json():
    payload = {
        "passed": False,
        "score": 0.4,
        "vulnerabilities": [
            {"severity": "high", "type": "sql_injection", "description": "f-string into cursor"},
        ],
        "recommendations": ["use parameterised queries"],
    }
    subagent = SecuritySubagent(llm_client=make_mock_llm(json.dumps(payload)))
    report = await subagent.run("cursor.execute(f'SELECT * FROM t WHERE id={uid}')")

    assert isinstance(report, SecurityReport)
    assert report.passed is False
    assert report.vulnerabilities[0]["severity"] == "high"
    assert report.recommendations == ["use parameterised queries"]


@pytest.mark.asyncio
async def test_security_defaults_when_fields_missing():
    subagent = SecuritySubagent(llm_client=make_mock_llm('{"passed": true, "score": 0.99}'))
    report = await subagent.run("x = 1")

    assert report.passed is True
    assert report.vulnerabilities == []
    assert report.recommendations == []
