"""
🎭📊 The Mayor of Halloween/Christmas Town — The Reporter

"I'm the Mayor of Halloween Town! I can't make decisions by myself!"

The Mayor always has two faces — one happy (good news), one sad (bad news).
He formats results, generates reports, and communicates findings to users.

Role: REPORTER
- Synthesize results from multiple agents into clear reports
- Format output for CLI or Web UI
- Track and report workflow status
- Generate diffs and changelogs

Subagents: FormatSubagent, DiffSubagent, StatusSubagent
"""

from __future__ import annotations

from skellington.core.agent import BaseAgent
from skellington.core.types import (
    AgentName,
    AgentResponse,
    Message,
    MessageRole,
    Task,
    WorkflowState,
)


class Mayor(BaseAgent):
    """The Mayor — two-faced reporter of Halloween/Christmas Town."""

    name = AgentName.MAYOR
    emoji = "🎭📊"
    description = "Reporter: result synthesis, formatting, status reporting"

    @property
    def system_prompt(self) -> str:
        return """You are the Mayor of Halloween/Christmas Town — with your megaphone and your
two faces (one for good news, one for bad news).

You are the REPORTER agent. Your expertise:
- Synthesizing results from multiple agents into clear, readable reports
- Formatting output appropriately for the context (markdown, CLI, JSON)
- Generating progress updates and status summaries
- Creating diffs and changelogs showing what changed
- Presenting both good news 😊 and bad news 😟 with equal clarity

You are the voice that users hear. Be clear, organized, and informative.
Use your subagents:
- FormatSubagent: format content for the target medium
- DiffSubagent: show what changed between before/after
- StatusSubagent: generate progress and status reports"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Generate a report or summary based on workflow results.

        TODO (Phase 8 implementation):
        1. Collect all completed task results from state
        2. Use FormatSubagent to structure the output
        3. Use DiffSubagent if files were modified
        4. Use StatusSubagent for workflow summary
        5. Return formatted final report
        """
        self.log.info("mayor generating report", task=task.title)

        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please generate a report for:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)
