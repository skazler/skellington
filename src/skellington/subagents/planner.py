"""
PlannerSubagent — decomposes a user request into ordered subtasks.

Parent: Jack (Orchestrator)
Learning goal: Task decomposition — breaking complex goals into atomic steps.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json


class Plan(BaseModel):
    """A decomposed plan with ordered steps."""

    goal: str
    steps: list[str]
    estimated_agents: list[str]  # Which agents will be needed


class PlannerSubagent(BaseSubAgent[Plan]):
    """Decomposes a high-level goal into an ordered list of executable steps."""

    name = "planner"
    parent_agent = AgentName.JACK
    emoji = "📋"
    description = "Breaks complex requests into ordered, actionable subtasks"

    @property
    def system_prompt(self) -> str:
        return """You are a precise task planner. Given a user's request, decompose it into
a clear, ordered list of subtasks. Each step should be atomic and assignable to one agent.

Available agents: jack (orchestrate), sally (build/code), oogie (research), zero (navigate),
lock/shock/barrel (validate), mayor (report).

Respond with ONLY a JSON object — no explanation, no markdown prose, no code fences:
{"goal": "...", "steps": ["step 1", "step 2", ...], "estimated_agents": ["agent1", ...]}"""

    async def run(self, request: str) -> Plan:
        """Decompose a request into a plan."""
        response = await self._call_llm(
            f"Decompose this request into an ordered plan:\n\n{request}",
            temperature=0.2,
        )
        try:
            data = extract_json(response)
            return Plan(**data)
        except (ValueError, KeyError, TypeError) as exc:
            self.log.warning("planner JSON parse failed, using fallback plan", error=str(exc))
            # Graceful degradation: treat the whole request as one step for Jack to handle directly
            return Plan(
                goal=request,
                steps=[request],
                estimated_agents=["jack"],
            )
