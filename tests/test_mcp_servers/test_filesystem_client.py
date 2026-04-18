"""
Integration tests for MCPFilesystemToolkit.

These actually spawn `python -m skellington.mcp_servers.filesystem.server` as
a subprocess and exercise the stdio MCP transport end-to-end. They are slower
than the in-process tool tests because of the subprocess spawn cost.

The child process reads `FILESYSTEM_ALLOWED_PATHS` from the env (JSON-encoded
by pydantic-settings) — we set it via `monkeypatch.setenv` so the server only
grants access to the per-test tmp directory.
"""

from __future__ import annotations

import json

import pytest

from skellington.mcp_servers.filesystem.client import MCPFilesystemToolkit, MCPToolError


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_filesystem_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("FILESYSTEM_ALLOWED_PATHS", json.dumps([str(tmp_path)]))

    target = tmp_path / "mcp_hello.txt"

    async with MCPFilesystemToolkit() as fs:
        written = await fs.write_file(str(target), "spooky-mcp")
        assert target.name in written

        content = await fs.read_file(str(target))
        assert content == "spooky-mcp"

        entries = await fs.list_directory(str(tmp_path))
        assert "mcp_hello.txt" in entries


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_filesystem_search(tmp_path, monkeypatch):
    monkeypatch.setenv("FILESYSTEM_ALLOWED_PATHS", json.dumps([str(tmp_path)]))

    (tmp_path / "a.py").write_text("import os\nimport sys\n")
    (tmp_path / "b.py").write_text("def foo(): pass\n")

    async with MCPFilesystemToolkit() as fs:
        results = await fs.search_files(str(tmp_path), r"^import\s+(\w+)", file_glob="**/*.py")

    assert any("import os" in r for r in results)
    assert any("import sys" in r for r in results)
    assert not any("foo" in r for r in results)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_filesystem_access_denied(tmp_path, tmp_path_factory, monkeypatch):
    """Access to paths outside FILESYSTEM_ALLOWED_PATHS surfaces as an MCPToolError."""
    monkeypatch.setenv("FILESYSTEM_ALLOWED_PATHS", json.dumps([str(tmp_path)]))

    forbidden = tmp_path_factory.mktemp("forbidden") / "secret.txt"
    forbidden.write_text("nope")

    async with MCPFilesystemToolkit() as fs:
        with pytest.raises(MCPToolError):
            await fs.read_file(str(forbidden))
