"""
StatusSubagent — generates workflow status and progress reports.

Parent: Mayor (Reporter)

Counts come from the workflow state itself (deterministic). The LLM only
produces the human narrative and next-steps suggestions.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, TaskStatus, WorkflowState
from skellington.utils.json_utils import extract_json


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
        return """You generate clear workflow status reports. Given task states,
write a one-paragraph narrative and a short list of next steps.

Respond with ONLY a JSON object — no prose, no fences:
{"narrative": str, "next_steps": [str]}"""

    async def run(self, state: WorkflowState) -> StatusReport:
        """Generate a status report from ``state``."""
        total = len(state.tasks)
        completed = sum(1 for t in state.tasks if t.status == TaskStatus.COMPLETE)
        failed = sum(1 for t in state.tasks if t.status == TaskStatus.FAILED)
        in_progress = sum(
            1
            for t in state.tasks
            if t.status
            in (
                TaskStatus.IN_PROGRESS,
                TaskStatus.PLANNING,
                TaskStatus.DELEGATED,
                TaskStatus.AWAITING_VALIDATION,
            )
        )
        pct = (completed / total * 100.0) if total else 0.0

        if total == 0:
            return StatusReport(
                total_tasks=0,
                completed=0,
                failed=0,
                in_progress=0,
                percentage_complete=0.0,
                narrative="No tasks have been queued yet.",
                next_steps=[],
            )

        task_summary = "\n".join(f"- [{t.status.value}] {t.title}" for t in state.tasks)
        response = await self._call_llm(
            f"Workflow has {total} tasks ({completed} done, {failed} failed, "
            f"{in_progress} in progress).\n\nTasks:\n{task_summary}",
            temperature=0.3,
        )
        data = extract_json(response)
        return StatusReport(
            total_tasks=total,
            completed=completed,
            failed=failed,
            in_progress=in_progress,
            percentage_complete=round(pct, 2),
            narrative=str(data.get("narrative", "Workflow in progress.")),
            next_steps=list(data.get("next_steps", [])),
        )
