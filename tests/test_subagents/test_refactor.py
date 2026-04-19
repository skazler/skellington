"""Tests for RefactorSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.refactor import RefactoredCode, RefactorSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_refactor_parses_llm_json():
    payload = {
        "code": "def add(a: int, b: int) -> int:\n    return a + b\n",
        "changes_made": ["Added type hints"],
        "behavior_preserved": True,
    }
    subagent = RefactorSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    result = await subagent.run("def add(a,b):\n    return a+b\n", goals=["add types"])

    assert isinstance(result, RefactoredCode)
    assert "int" in result.code
    assert result.changes_made == ["Added type hints"]
    assert result.behavior_preserved is True


@pytest.mark.asyncio
async def test_refactor_defaults_when_fields_missing():
    partial = '{"code": "pass"}'
    subagent = RefactorSubagent(llm_client=make_mock_llm(partial))
    result = await subagent.run("old code")

    assert result.code == "pass"
    assert result.changes_made == []
    assert result.behavior_preserved is True
