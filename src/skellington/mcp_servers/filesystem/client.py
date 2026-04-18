"""
MCPFilesystemToolkit — orthodox MCP client for the filesystem server.

Phase 3.5: instead of calling `tools.py` in-process, Zero can go through a
real subprocess running `server.py` and speak to it over stdio, exactly like
any MCP-compliant host would. Same method names as the `tools` module — so
subagents accept either one as their `fs` toolkit without change.

Lifecycle: async context manager. Open it once per Zero.run() and let all
three subagents share the single client session.

    async with MCPFilesystemToolkit() as fs:
        await fs.read_file("/path")
"""

from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from typing import Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


class MCPToolError(RuntimeError):
    """The MCP server reported an error or returned an unexpected response shape."""


class MCPFilesystemToolkit:
    """
    Async context manager that spawns the filesystem MCP server as a subprocess
    and exposes the same async method surface as `mcp_servers.filesystem.tools`.

    Spawn once per logical task; closing the context terminates the subprocess.
    """

    def __init__(
        self,
        python_executable: str | None = None,
        server_module: str = "skellington.mcp_servers.filesystem.server",
        env: dict[str, str] | None = None,
    ) -> None:
        self._python = python_executable or sys.executable
        self._server_module = server_module
        # MCP's get_default_environment() whitelists a small set of system vars and
        # drops everything else — including our Skellington config. We pass the full
        # parent environment through so the child sees FILESYSTEM_ALLOWED_PATHS,
        # ANTHROPIC_API_KEY, etc.
        self._env = env if env is not None else dict(os.environ)
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self) -> Self:
        self._stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command=self._python,
            args=["-m", self._server_module],
            env=self._env,
        )
        read, write = await self._stack.enter_async_context(stdio_client(server_params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._session = None
        self._stack = None

    # ------------------------------------------------------------------
    # Toolkit surface — mirrors mcp_servers.filesystem.tools
    # ------------------------------------------------------------------

    async def read_file(self, path: str) -> str:
        text = await self._call("read_file", {"path": path})
        if text.startswith("Error:"):
            raise MCPToolError(text)
        return text

    async def write_file(self, path: str, content: str) -> str:
        text = await self._call("write_file", {"path": path, "content": content})
        if text.startswith("Error:"):
            raise MCPToolError(text)
        # server.py prefixes successful writes with "Written: "; strip it to match tools.write_file
        return text.removeprefix("Written: ").strip()

    async def list_directory(self, path: str, recursive: bool = False) -> list[str]:
        text = await self._call("list_directory", {"path": path, "recursive": recursive})
        if text.startswith("Error:"):
            raise MCPToolError(text)
        return [line for line in text.splitlines() if line]

    async def search_files(
        self,
        directory: str,
        pattern: str,
        file_glob: str = "**/*",
    ) -> list[str]:
        text = await self._call(
            "search_files",
            {"directory": directory, "pattern": pattern, "file_glob": file_glob},
        )
        if text.startswith("Error:"):
            raise MCPToolError(text)
        if text == "No matches":
            return []
        return [line for line in text.splitlines() if line]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _call(self, name: str, arguments: dict) -> str:
        if self._session is None:
            raise RuntimeError(
                "MCPFilesystemToolkit used outside its async context — "
                "call `async with MCPFilesystemToolkit() as fs:` first."
            )
        result = await self._session.call_tool(name, arguments)

        # MCP call_tool returns a CallToolResult with .content: list[TextContent|...].
        # Our server only ever emits TextContent, so we concatenate text blocks.
        chunks: list[str] = []
        for block in result.content:
            if isinstance(block, TextContent):
                chunks.append(block.text)
        if not chunks:
            raise MCPToolError(f"MCP tool {name!r} returned no text content")
        return "\n".join(chunks)
