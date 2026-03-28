"""
StatusSubagent — generates workflow status and progress reports.

Parent: Mayor (Reporter)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, WorkflowState


class StatusReport(BaseModel):
    total_tasks: int
    completed: int
    failed: int
    in_progress: int
    percentage_complete: float
    narrative: str
    next_steps: list[str]


class StatusSubagent(BaseSubAgent[StatusReport]):
    """Generates workflow status and progress reports."""

    name = "status"
    parent_agent = AgentName.MAYOR
    emoji = "📈"
    description = "Tracks and reports workflow progress"

    @property
    def system_prompt(self) -> str:
        return """You generate clear workflow status reports. Analyze task states and
produce a readable progress summary.
Respond with JSON: {"total_tasks": int, "completed": int, "failed": int,
"in_progress": int, "percentage_complete": float, "narrative": str, "next_steps": [str]}"""

    async def run(self, state: WorkflowState) -> StatusReport:
        """Generate a status report from workflow state."""
        task_summary = "\n".join(f"- [{t.status.value}] {t.title}" for t in state.tasks)
        response = await self._call_llm(
            f"Generate a status report for this workflow:\n\n{task_summary}",
            temperature=0.3,
        )
        import json

        data = json.loads(response)
        return StatusReport(**data)
