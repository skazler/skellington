"""
ContextSubagent — assembles relevant context windows for other agents.

Parent: Zero (Navigator)
Learning goal: Context window management — what to include for best results.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class ContextWindow(BaseModel):
    task: str
    relevant_files: list[dict[str, str]]  # [{"path": ..., "content": ..., "reason": ...}]
    total_tokens_estimate: int
    summary: str


class ContextSubagent(BaseSubAgent[ContextWindow]):
    """Assembles the most relevant context for a given task."""

    name = "context"
    parent_agent = AgentName.ZERO
    emoji = "🎯"
    description = "Selects and assembles the most relevant context for a task"

    @property
    def system_prompt(self) -> str:
        return """You are a context selection expert. Given a task and available files,
select ONLY the most relevant content to include in the context window.
More context is not always better — be selective and purposeful.
Respond with JSON: {"task": str,
"relevant_files": [{"path": str, "content": str, "reason": str}],
"total_tokens_estimate": int, "summary": str}"""

    async def run(self, task: str, available_files: list[str]) -> ContextWindow:
        """Build an optimal context window for the task."""
        files_text = "\n".join(available_files)
        response = await self._call_llm(
            f"Task: {task}\n\nAvailable files:\n{files_text}\n\nSelect the most relevant files.",
        )
        import json

        data = json.loads(response)
        return ContextWindow(**data)
