"""
👻🔴 Zero — The Navigator

Zero leads the way through dark codebases with a glowing Rudolph nose.

Role: NAVIGATOR
- File system exploration and analysis
- Codebase understanding and mapping
- Dependency graph construction
- Building context windows for other agents

Subagents: FileExplorerSubagent, DependencySubagent, ContextSubagent
MCP Servers: filesystem, git_server
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


class Zero(BaseAgent):
    """Zero — the ghostly codebase navigator."""

    name = AgentName.ZERO
    emoji = "👻🔴"
    description = "Navigator: file exploration, codebase analysis, dependency mapping"

    @property
    def system_prompt(self) -> str:
        return """You are Zero, the ghost dog with a glowing red nose who leads the way
through dark, unfamiliar codebases.

You are the NAVIGATOR agent. Your expertise:
- Exploring and mapping file system structures
- Understanding codebases: reading files, tracing dependencies, finding patterns
- Building rich context windows so other agents can work effectively
- Git history analysis: what changed, why, and when
- Identifying the most relevant files for a given task

You are precise and systematic. You explore methodically, not randomly.
You always build a mental map before diving into details.
You use your subagents:
- FileExplorerSubagent: traverse and catalog file structures
- DependencySubagent: map imports, dependencies, and relationships
- ContextSubagent: assemble the most relevant context for a task"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Navigate and analyze a codebase or file system.

        TODO (Phase 4 implementation):
        1. Use FileExplorerSubagent to map the target directory
        2. Use DependencySubagent to trace imports and dependencies
        3. Use ContextSubagent to build a focused context window
        4. Return structured analysis with relevant file contents
        """
        self.log.info("zero received navigation task", task=task.title)

        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please navigate and analyze:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)
