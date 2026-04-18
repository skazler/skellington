"""Tests for ContextSubagent."""

from __future__ import annotations

import pytest

from skellington.subagents.context import ContextSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_context_reads_llm_selected_files(allowed_tmp_path):
    keep = allowed_tmp_path / "keep.py"
    keep.write_text("important content")
    skip = allowed_tmp_path / "skip.py"
    skip.write_text("noise")

    selection_json = (
        f'{{"files": [{{"path": "{str(keep).replace(chr(92), "/")}", '
        f'"reason": "entry point"}}]}}'
    )
    # The subagent parses with extract_json, which accepts single-forward-slash paths
    # whether or not the path is Windows-native.
    subagent = ContextSubagent(llm_client=make_mock_llm(selection_json))
    window = await subagent.run("understand the entry point", [str(keep), str(skip)])

    assert len(window.relevant_files) == 1
    assert window.relevant_files[0]["path"].endswith("keep.py")
    assert window.relevant_files[0]["content"] == "important content"
    assert window.relevant_files[0]["reason"] == "entry point"


@pytest.mark.asyncio
async def test_context_empty_candidates_shortcircuits(allowed_tmp_path):
    subagent = ContextSubagent(llm_client=make_mock_llm("unused"))
    window = await subagent.run("anything", [])
    assert window.relevant_files == []
    assert window.total_tokens_estimate == 0


@pytest.mark.asyncio
async def test_context_falls_back_when_llm_returns_garbage(allowed_tmp_path):
    good = allowed_tmp_path / "good.py"
    good.write_text("x = 1")
    noise = allowed_tmp_path / "noise.log"
    noise.write_text("nope")

    subagent = ContextSubagent(llm_client=make_mock_llm("not json at all"))
    window = await subagent.run("task", [str(good), str(noise)])

    # Fallback picks .py/.md/.toml files only
    assert len(window.relevant_files) == 1
    assert window.relevant_files[0]["path"].endswith("good.py")
    assert window.relevant_files[0]["reason"] == "heuristic fallback"


@pytest.mark.asyncio
async def test_context_truncates_large_files(allowed_tmp_path):
    big = allowed_tmp_path / "big.py"
    big.write_text("a" * 50_000)

    path_str = str(big).replace(chr(92), "/")
    selection_json = f'{{"files": [{{"path": "{path_str}", "reason": "huge"}}]}}'
    subagent = ContextSubagent(llm_client=make_mock_llm(selection_json))
    window = await subagent.run("task", [str(big)])

    assert len(window.relevant_files) == 1
    assert "[truncated]" in window.relevant_files[0]["content"]
