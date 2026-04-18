"""Tests for FileExplorerSubagent."""

from __future__ import annotations

import pytest

from skellington.subagents.file_explorer import FileExplorerSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_file_explorer_buckets_by_directory(allowed_tmp_path):
    (allowed_tmp_path / "a.py").write_text("x")
    (allowed_tmp_path / "b.md").write_text("y")
    pkg = allowed_tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "c.py").write_text("z")

    subagent = FileExplorerSubagent(llm_client=make_mock_llm("a python project summary"))
    tree = await subagent.run(str(allowed_tmp_path))

    assert tree.root_path == str(allowed_tmp_path)
    assert tree.total_files == 3
    assert tree.file_types == {"py": 2, "md": 1}
    # top-level files land in "."
    assert "a.py" in tree.tree["."]
    assert "b.md" in tree.tree["."]
    # nested files land under their directory (path separator normalized)
    pkg_bucket = tree.tree.get("pkg") or tree.tree.get("pkg/") or []
    assert "c.py" in pkg_bucket
    assert tree.summary == "a python project summary"


@pytest.mark.asyncio
async def test_file_explorer_skips_ignored_dirs(allowed_tmp_path):
    (allowed_tmp_path / "keep.py").write_text("x")
    noise = allowed_tmp_path / "__pycache__"
    noise.mkdir()
    (noise / "junk.pyc").write_text("garbage")

    subagent = FileExplorerSubagent(llm_client=make_mock_llm("summary"))
    tree = await subagent.run(str(allowed_tmp_path))

    assert tree.total_files == 1
    assert "__pycache__" not in tree.tree


@pytest.mark.asyncio
async def test_file_explorer_summary_falls_back_on_llm_error(allowed_tmp_path):
    (allowed_tmp_path / "only.py").write_text("x")

    llm = make_mock_llm()
    llm.complete.side_effect = RuntimeError("model down")

    subagent = FileExplorerSubagent(llm_client=llm)
    tree = await subagent.run(str(allowed_tmp_path))

    assert tree.total_files == 1
    assert "1 files" in tree.summary  # heuristic fallback mentions counts
