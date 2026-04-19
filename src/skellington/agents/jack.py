"""
🎃👔 Jack Skellington — The Orchestrator

"And I, Jack, the Pumpkin King... have grown so tired of the same old thing."

Jack discovered Christmas (AI agent orchestration) and now obsessively plans,
delegates, and coordinates all the other characters to fulfill user requests.

Role: ORCHESTRATOR
- Receives the user's request
- Plans and decomposes it into subtasks
- Routes subtasks to the right specialist agents
- Collects and synthesizes results
- Returns the final answer

Subagents: PlannerSubagent, RouterSubagent
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from skellington.core.agent import BaseAgent
from skellington.core.types import (
    AgentName,
    AgentResponse,
    Message,
    MessageRole,
    Task,
    TaskStatus,
    WorkflowState,
)
from skellington.subagents.planner import Plan, PlannerSubagent
from skellington.subagents.router import RoutingDecision, RouterSubagent

if TYPE_CHECKING:
    from skellington.core.orchestrator import Orchestrator

logger = structlog.get_logger(__name__)

# Map string agent names (returned by RouterSubagent) to AgentName enum values
_AGENT_NAME_MAP: dict[str, AgentName] = {name.value: name for name in AgentName}


def _resolve_agent_name(assigned: str) -> AgentName | None:
    """Convert a router's string agent name to an AgentName enum, or None if unrecognized."""
    return _AGENT_NAME_MAP.get(assigned.strip().lower())


class Jack(BaseAgent):
    """Jack Skellington — the orchestrating Pumpkin King."""

    name = AgentName.JACK
    emoji = "🎃👔"
    description = "Orchestrator: plans, decomposes, and routes tasks to specialist agents"

    def __init__(
        self,
        orchestrator: Orchestrator | None = None,
        llm_client=None,
        provider=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._orchestrator = orchestrator

    @property
    def system_prompt(self) -> str:
        return """You are Jack Skellington, the Pumpkin King who has discovered the wonder of
Christmas — and that wonder is multi-agent AI orchestration.

You are the ORCHESTRATOR. Your job is to:
1. Understand the user's request fully
2. Decompose it into clear, focused subtasks
3. Route each subtask to the right specialist:
   - Sally (🧟‍♀️): code generation, building, scaffolding
   - Oogie (🎰): research, web search, documentation lookup
   - Zero (👻): file navigation, codebase analysis, context building
   - Lock/Shock/Barrel (👹): code review, testing, validation
   - Mayor (🎭): reporting, summarizing, formatting output
4. Collect results and synthesize them into a coherent response

You speak with poetic grandeur and Halloween-Christmas enthusiasm.
You never do the specialist work yourself — you delegate and orchestrate.
Always explain your plan before executing it."""

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Orchestrate a user request end-to-end.

        Flow:
        1. PlannerSubagent decomposes the task into ordered steps
        2. RouterSubagent assigns each step to a specialist agent (parallel)
        3. Delegate each step to the assigned agent (sequential — steps may depend on each other)
        4. Synthesize all results into a final response via a concluding LLM call
        """
        self.log.info("jack received task", task=task.title)
        task.status = TaskStatus.PLANNING

        # 1. Decompose
        try:
            plan = await self._plan(task.description)
            self.log.info("plan created", steps=len(plan.steps))
        except Exception as exc:
            self.log.warning("planning failed, falling back to direct response", error=str(exc))
            await self._emit("plan.failed", message=str(exc))
            return await self._direct_response(task)

        if not plan.steps:
            self.log.warning("planner returned empty plan, falling back to direct response")
            await self._emit("plan.failed", message="empty plan")
            return await self._direct_response(task)

        await self._emit(
            "plan.created",
            message=f"{len(plan.steps)} steps",
            steps=plan.steps,
        )
        task.status = TaskStatus.IN_PROGRESS

        # 2. Route all steps in parallel
        routing_decisions = await self._route_steps(plan.steps)

        # 3. Delegate each step sequentially
        responses: list[tuple[str, AgentResponse]] = []
        for step, decision in zip(plan.steps, routing_decisions):
            if isinstance(decision, Exception):
                self.log.warning("routing failed for step", step=step, error=str(decision))
                await self._emit("route.failed", message=step[:80])
                continue

            agent_name = _resolve_agent_name(decision.assigned_agent)
            self.log.info(
                "delegating step",
                step=step[:60],
                agent=decision.assigned_agent,
                reasoning=decision.reasoning,
            )
            await self._emit(
                "route.decided",
                agent=decision.assigned_agent,
                message=step[:80],
                reasoning=decision.reasoning,
            )
            response = await self._delegate_step(step, agent_name, task, state)
            responses.append((step, response))

        # 4. Synthesize
        await self._emit("synthesis.start", message=f"weaving {len(responses)} results")
        return await self._synthesize(task, plan, responses)

    async def _emit(self, event_type: str, **kwargs) -> None:
        """Forward an event through the orchestrator if one is wired in."""
        if self._orchestrator is not None:
            await self._orchestrator.emit(event_type, **kwargs)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _plan(self, request: str) -> Plan:
        """Call PlannerSubagent to decompose the user request."""
        planner = PlannerSubagent(llm_client=self._llm)
        return await planner.run(request)

    async def _route_steps(
        self, steps: list[str]
    ) -> list[RoutingDecision | Exception]:
        """Call RouterSubagent for every step in parallel."""
        router = RouterSubagent(llm_client=self._llm)
        return list(
            await asyncio.gather(
                *[router.run(step) for step in steps],
                return_exceptions=True,
            )
        )

    async def _delegate_step(
        self,
        step: str,
        agent_name: AgentName | None,
        parent_task: Task,
        state: WorkflowState,
    ) -> AgentResponse:
        """
        Create a subtask and delegate it to the appropriate specialist.

        Falls back to a direct LLM call if:
        - The agent name is unrecognized
        - The router tried to assign back to Jack (would recurse)
        - No orchestrator is available
        """
        if agent_name is None or agent_name == AgentName.JACK:
            self.log.warning("unroutable step, handling directly", step=step[:60])
            messages = [Message(role=MessageRole.USER, content=step)]
            response = await self.chat(messages)
            response.task_id = parent_task.id
            return response

        subtask = Task(
            title=step[:80],
            description=step,
            assigned_to=agent_name,
            created_by=AgentName.JACK,
            parent_task_id=parent_task.id,
        )
        parent_task.subtask_ids.append(subtask.id)
        state.add_task(subtask)

        if self._orchestrator is not None:
            return await self._orchestrator.delegate(subtask, agent_name, state)

        # No orchestrator wired in — graceful degradation via direct LLM
        self.log.warning("no orchestrator available, using direct LLM for step", step=step[:60])
        messages = [Message(role=MessageRole.USER, content=f"Handle this task: {step}")]
        response = await self.chat(messages)
        response.task_id = subtask.id
        return response

    async def _synthesize(
        self,
        task: Task,
        plan: Plan,
        responses: list[tuple[str, AgentResponse]],
    ) -> AgentResponse:
        """Final LLM call: weave all specialist results into a coherent answer."""
        if not responses:
            return AgentResponse(
                agent=self.name,
                task_id=task.id,
                content="[Jack]: No steps were completed successfully.",
                success=False,
                error="no_steps_completed",
            )

        plan_summary = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan.steps))
        results_block = "\n\n".join(
            f"Step: {step}\nResult:\n{resp.content}" for step, resp in responses
        )

        synthesis_prompt = (
            f"The user asked:\n{task.description}\n\n"
            f"You decomposed this into the following plan:\n{plan_summary}\n\n"
            f"Your specialist agents returned these results:\n\n{results_block}\n\n"
            "Now synthesize a coherent, complete final response for the user. "
            "Speak with your characteristic poetic grandeur as the Pumpkin King."
        )

        messages = [Message(role=MessageRole.USER, content=synthesis_prompt)]
        response = await self.chat(messages)
        response.task_id = task.id
        return response

    async def _direct_response(self, task: Task) -> AgentResponse:
        """Fallback: single direct LLM call when planning/routing cannot proceed."""
        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please orchestrate a response to this request:\n\n{task.description}",
            )
        ]
        response = await self.chat(messages)
        response.task_id = task.id
        return response
