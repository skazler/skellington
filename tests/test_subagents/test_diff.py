"""Tests for DiffSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.diff import DiffReport, DiffSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_diff_computes_unified_diff_deterministically():
    """The diff text comes from difflib, not the LLM (LLMs hallucinate diffs)."""
    before = "def add(a, b):\n    return a + b\n"
    after = "def add(a: int, b: int) -> int:\n    return a + b\n"
    subagent = DiffSubagent(
        llm_client=make_mock_llm('{"change_summary": "added type hints"}')
    )

    report = await subagent.run(before, after, filename="math.py")

    assert isinstance(report, DiffReport)
    assert report.files_changed == ["math.py"]
    # +1 hunk header (+++) is excluded; the type-annotated line is the only addition.
    assert report.additions == 1
    assert report.deletions == 1
    assert "def add(a: int" in report.diff_text
    assert report.change_summary == "added type hints"


@pytest.mark.asyncio
async def test_diff_short_circuits_when_unchanged():
    """No textual diff → no LLM call, empty report."""
    llm = make_mock_llm("should not be called")
    subagent = DiffSubagent(llm_client=llm)

    report = await subagent.run("same\n", "same\n", filename="x.py")

    assert report.files_changed == []
    assert report.additions == 0
    assert report.deletions == 0
    assert report.diff_text == ""
    assert report.change_summary == "No changes."
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_diff_defaults_summary_when_llm_omits_it():
    subagent = DiffSubagent(llm_client=make_mock_llm("{}"))
    report = await subagent.run("a\n", "b\n", filename="x")
    assert report.change_summary == "Changes applied."
