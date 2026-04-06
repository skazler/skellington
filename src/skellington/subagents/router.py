"""
RouterSubagent — decides which agent should handle each task step.

Parent: Jack (Orchestrator)
Learning goal: Intelligent routing based on task semantics.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json

# All valid agent names the router may return
_VALID_AGENTS = {a.value for a in AgentName}


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
- lock: logic and correctness review
- shock: style, maintainability, and test coverage review
- barrel: security and robustness review
- mayor: reporting, summarizing results, formatting output

Respond with ONLY a JSON object — no explanation, no markdown prose, no code fences:
{"step": "...", "assigned_agent": "agent_name", "reasoning": "..."}"""

    async def run(self, step: str) -> RoutingDecision:
        """Route a step to the best agent."""
        response = await self._call_llm(
            f"Route this task step to the best agent:\n\n{step}",
            temperature=0.1,
        )
        try:
            data = extract_json(response)
            decision = RoutingDecision(**data)
            # Validate the agent name is one we recognise; fall back to mayor (reporter) if not
            if decision.assigned_agent not in _VALID_AGENTS:
                self.log.warning(
                    "router returned unknown agent, falling back to mayor",
                    returned=decision.assigned_agent,
                )
                decision = RoutingDecision(
                    step=step,
                    assigned_agent="mayor",
                    reasoning="fallback: unrecognised agent name",
                )
            return decision
        except (ValueError, KeyError, TypeError) as exc:
            self.log.warning("router JSON parse failed, defaulting to mayor", error=str(exc))
            return RoutingDecision(
                step=step,
                assigned_agent="mayor",
                reasoning=f"fallback: parse error ({exc})",
            )
