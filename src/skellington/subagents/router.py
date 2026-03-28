"""
RouterSubagent — decides which agent should handle each task step.

Parent: Jack (Orchestrator)
Learning goal: Intelligent routing based on task semantics.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class RoutingDecision(BaseModel):
    """A routing decision for a single task step."""

    step: str
    assigned_agent: str
    reasoning: str


class RouterSubagent(BaseSubAgent[RoutingDecision]):
    """Routes a task step to the most appropriate specialist agent."""

    name = "router"
    parent_agent = AgentName.JACK
    emoji = "🔀"
    description = "Routes task steps to the most appropriate specialist agent"

    @property
    def system_prompt(self) -> str:
        return """You are a routing expert. Given a task step, decide which agent should handle it.

Agent capabilities:
- sally: code generation, file creation, project scaffolding, refactoring
- oogie: web research, documentation, library comparison, finding information
- zero: file exploration, reading existing code, dependency analysis
- lock/shock/barrel: code review, testing, security analysis, validation
- mayor: reporting, summarizing results, formatting output

Respond with JSON: {"step": str, "assigned_agent": str, "reasoning": str}"""

    async def run(self, step: str) -> RoutingDecision:
        """Route a step to the best agent."""
        response = await self._call_llm(
            f"Route this task step to the best agent:\n\n{step}",
            temperature=0.1,
        )
        import json

        data = json.loads(response)
        return RoutingDecision(**data)
