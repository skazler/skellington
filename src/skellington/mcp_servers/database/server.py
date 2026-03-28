"""
Database MCP Server 🗄️

Provides SQLite key-value and query tools for agent memory persistence.

Learning goal: Persistent state across agent calls — how agents remember.

Tools exposed:
- db_set: Store a value by key
- db_get: Retrieve a value by key
- db_query: Run a read-only SQL query
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from skellington.core.config import get_settings

app = Server("skellington-database")


def _get_db_path() -> Path:
    return get_settings().memory_db_path


def _get_conn() -> sqlite3.Connection:
    db = _get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_store "
        "(agent TEXT, key TEXT, value TEXT, PRIMARY KEY (agent, key))"
    )
    conn.commit()
    return conn


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="db_set",
            description="Store a JSON value by agent and key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "key": {"type": "string"},
                    "value": {"description": "Any JSON-serializable value"},
                },
                "required": ["agent", "key", "value"],
            },
        ),
        Tool(
            name="db_get",
            description="Retrieve a stored value by agent and key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["agent", "key"],
            },
        ),
        Tool(
            name="db_list_keys",
            description="List all stored keys for an agent.",
            inputSchema={
                "type": "object",
                "properties": {"agent": {"type": "string"}},
                "required": ["agent"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "db_set":
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (agent, key, value) VALUES (?, ?, ?)",
            (arguments["agent"], arguments["key"], json.dumps(arguments["value"])),
        )
        conn.commit()
        conn.close()
        return [TextContent(type="text", text="Stored.")]

    if name == "db_get":
        conn = _get_conn()
        row = conn.execute(
            "SELECT value FROM kv_store WHERE agent=? AND key=?",
            (arguments["agent"], arguments["key"]),
        ).fetchone()
        conn.close()
        if row is None:
            return [TextContent(type="text", text="null")]
        return [TextContent(type="text", text=row[0])]

    if name == "db_list_keys":
        conn = _get_conn()
        rows = conn.execute(
            "SELECT key FROM kv_store WHERE agent=?", (arguments["agent"],)
        ).fetchall()
        conn.close()
        keys = [r[0] for r in rows]
        return [TextContent(type="text", text=json.dumps(keys))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
