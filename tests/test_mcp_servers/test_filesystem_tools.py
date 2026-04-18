"""Tests for the pure filesystem tool functions in mcp_servers/filesystem/tools.py."""

from __future__ import annotations

import pytest

from skellington.mcp_servers.filesystem import tools


@pytest.mark.asyncio
async def test_read_and_write_roundtrip(allowed_tmp_path):
    target = allowed_tmp_path / "hello.txt"
    await tools.write_file(str(target), "spooky")
    assert await tools.read_file(str(target)) == "spooky"


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(allowed_tmp_path):
    nested = allowed_tmp_path / "a" / "b" / "c.txt"
    await tools.write_file(str(nested), "deep")
    assert nested.read_text() == "deep"


@pytest.mark.asyncio
async def test_list_directory_shallow_and_recursive(allowed_tmp_path):
    (allowed_tmp_path / "top.py").write_text("x")
    (allowed_tmp_path / "sub").mkdir()
    (allowed_tmp_path / "sub" / "nested.py").write_text("y")

    shallow = await tools.list_directory(str(allowed_tmp_path))
    assert "top.py" in shallow
    assert "sub" in shallow
    assert "sub/nested.py" not in shallow

    recursive = await tools.list_directory(str(allowed_tmp_path), recursive=True)
    # On Windows glob produces backslashes; normalize for the assertion
    recursive_norm = {entry.replace("\\", "/") for entry in recursive}
    assert "sub/nested.py" in recursive_norm


@pytest.mark.asyncio
async def test_search_files_regex(allowed_tmp_path):
    (allowed_tmp_path / "a.py").write_text("import os\nimport sys\n")
    (allowed_tmp_path / "b.py").write_text("def foo(): pass\n")

    results = await tools.search_files(
        str(allowed_tmp_path),
        r"^import\s+(\w+)",
        file_glob="**/*.py",
    )
    assert any("import os" in r for r in results)
    assert any("import sys" in r for r in results)
    assert not any("foo" in r for r in results)


@pytest.mark.asyncio
async def test_access_denied_outside_allowed_root(allowed_tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("forbidden") / "secret.txt"
    outside.write_text("nope")
    with pytest.raises(tools.FilesystemAccessError):
        await tools.read_file(str(outside))
