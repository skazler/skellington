"""
FileExplorerSubagent — traverses and catalogs file system structures.

Parent: Zero (Navigator)
Learning goal: MCP filesystem server integration.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class FileTree(BaseModel):
    root_path: str
    tree: dict[str, list[str]]  # directory -> [files]
    total_files: int
    file_types: dict[str, int]  # extension -> count
    summary: str


class FileExplorerSubagent(BaseSubAgent[FileTree]):
    """Traverses and catalogs file system structures via filesystem MCP."""

    name = "file_explorer"
    parent_agent = AgentName.ZERO
    emoji = "📂"
    description = "Traverses and maps file system structures"

    @property
    def system_prompt(self) -> str:
        return """You are a file system explorer. Map directory structures clearly.
TODO: Connect to filesystem MCP server for real directory traversal.
Respond with JSON: {"root_path": str, "tree": {"dir": ["file"]},
"total_files": int, "file_types": {"ext": count}, "summary": str}"""

    async def run(self, path: str, max_depth: int = 3) -> FileTree:
        """Explore the file tree at the given path."""
        # TODO: Replace with actual filesystem MCP tool call
        response = await self._call_llm(
            f"Describe the file structure you would expect at: {path} (max depth: {max_depth})",
        )
        import json

        data = json.loads(response)
        return FileTree(**data)
