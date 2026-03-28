"""Tests for the filesystem MCP server."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_allowed(tmp_path):
    """Patch allowed paths to include tmp_path."""
    with patch(
        "skellington.mcp_servers.filesystem.server.get_settings",
        return_value=type("S", (), {"filesystem_allowed_paths": [str(tmp_path)]})(),
    ):
        yield tmp_path


@pytest.mark.asyncio
async def test_read_write_file(tmp_allowed):
    from skellington.mcp_servers.filesystem.server import call_tool

    write_result = await call_tool(
        "write_file",
        {"path": str(tmp_allowed / "test.txt"), "content": "hello skellington"},
    )
    assert "Written" in write_result[0].text

    read_result = await call_tool("read_file", {"path": str(tmp_allowed / "test.txt")})
    assert "hello skellington" in read_result[0].text


@pytest.mark.asyncio
async def test_list_directory(tmp_allowed):
    from skellington.mcp_servers.filesystem.server import call_tool

    (tmp_allowed / "a.py").write_text("a")
    (tmp_allowed / "b.py").write_text("b")

    result = await call_tool("list_directory", {"path": str(tmp_allowed)})
    assert "a.py" in result[0].text
    assert "b.py" in result[0].text
