"""
Code Execution MCP Server ⚡

Provides sandboxed Python code execution for Lock, Shock & Barrel validators.

Learning goal: Safety patterns for code execution — timeouts, resource limits,
subprocess isolation.

Tools exposed:
- execute_python: Run Python code in a subprocess with timeout
- run_pytest: Run pytest on a test file
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.core.config import get_settings

app = Server("skellington-code-exec")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="execute_python",
            description="Execute Python code in a sandboxed subprocess with a timeout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="run_pytest",
            description="Run pytest on a Python test file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_code": {"type": "string", "description": "Test file contents"},
                    "source_code": {"type": "string", "description": "Source code being tested"},
                    "timeout": {"type": "integer", "default": 60},
                },
                "required": ["test_code"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    settings = get_settings()

    if name == "execute_python":
        code = arguments["code"]
        timeout = min(arguments.get("timeout", 30), settings.code_exec_timeout)

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return [TextContent(type="text", text=f"Execution timed out after {timeout}s")]

            output = stdout.decode()
            errors = stderr.decode()
            result = f"STDOUT:\n{output}\nSTDERR:\n{errors}\nExit code: {proc.returncode}"
            return [TextContent(type="text", text=result)]
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    if name == "run_pytest":
        test_code = arguments["test_code"]
        source_code = arguments.get("source_code", "")
        timeout = min(arguments.get("timeout", 60), settings.code_exec_timeout * 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if source_code:
                (tmp / "source.py").write_text(source_code)
            (tmp / "test_source.py").write_text(test_code)

            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "pytest",
                str(tmp / "test_source.py"),
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return [TextContent(type="text", text=f"pytest timed out after {timeout}s")]

            return [TextContent(type="text", text=stdout.decode() + stderr.decode())]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
