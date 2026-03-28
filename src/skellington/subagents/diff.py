"""
DiffSubagent — generates readable diffs showing before/after changes.

Parent: Mayor (Reporter)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class DiffReport(BaseModel):
    files_changed: list[str]
    additions: int
    deletions: int
    diff_text: str
    change_summary: str


class DiffSubagent(BaseSubAgent[DiffReport]):
    """Generates readable diffs between before and after states."""

    name = "diff"
    parent_agent = AgentName.MAYOR
    emoji = "📊"
    description = "Generates readable diffs and changelogs"

    @property
    def system_prompt(self) -> str:
        return """You are a diff expert. Given before and after versions of code or content,
generate a clear, readable diff showing what changed.
Respond with JSON: {"files_changed": [str], "additions": int, "deletions": int,
"diff_text": str, "change_summary": str}"""

    async def run(self, before: str, after: str, filename: str = "file") -> DiffReport:
        """Generate a diff between before and after."""
        response = await self._call_llm(
            f"Generate a diff for '{filename}':\n\nBEFORE:\n{before}\n\nAFTER:\n{after}",
        )
        import json

        data = json.loads(response)
        return DiffReport(**data)
