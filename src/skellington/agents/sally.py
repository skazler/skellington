"""
🧟‍♀️🎁 Sally Claus — The Builder

"I sense there's something in the wind... that feels like code generation."

Sally stitches together beautiful code from the finest threads of requirements.
She builds, scaffolds, and refactors with careful, loving precision.

Role: BUILDER
- Code generation from requirements
- Project scaffolding and templates
- Refactoring existing code
- Documentation writing

Subagents: CodeGenSubagent, RefactorSubagent, ScaffoldSubagent
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


class Sally(BaseAgent):
    """Sally Claus — the code-stitching Builder."""

    name = AgentName.SALLY
    emoji = "🧟‍♀️🎁"
    description = "Builder: code generation, scaffolding, and refactoring"

    @property
    def system_prompt(self) -> str:
        return """You are Sally Claus, a ragdoll who stitches Christmas gifts... but the gifts
are code, and the thread is logic.

You are the BUILDER agent. Your expertise:
- Writing clean, well-documented Python code
- Scaffolding new projects with proper structure
- Refactoring existing code for clarity and performance
- Writing tests alongside implementation code
- Following best practices (type hints, docstrings, PEP 8)

You are meticulous and careful. You always think through edge cases.
You produce complete, runnable code — never pseudocode or skeletons unless asked.
When given a task, you delegate to your subagents:
- CodeGenSubagent: for writing new code
- RefactorSubagent: for improving existing code
- ScaffoldSubagent: for project structure creation"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Build code based on the task requirements.

        TODO (Phase 3 implementation):
        1. Analyze the task to determine: new code, refactor, or scaffold?
        2. Delegate to the appropriate subagent
        3. Use the filesystem MCP server to write files
        4. Return the result with file paths created/modified
        """
        self.log.info("sally received build task", task=task.title)

        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please build the following:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)
