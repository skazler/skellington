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

import structlog

from skellington.core.agent import BaseAgent
from skellington.core.types import (
    AgentName,
    AgentResponse,
    Task,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


class Jack(BaseAgent):
    """Jack Skellington — the orchestrating Pumpkin King."""

    name = AgentName.JACK
    emoji = "🎃👔"
    description = "Orchestrator: plans, decomposes, and routes tasks to specialist agents"

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

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Orchestrate a user request end-to-end.

        TODO (Phase 2 implementation):
        1. Call PlannerSubagent to decompose the task
        2. Call RouterSubagent to assign subtasks to agents
        3. Use self._orchestrator.delegate() for each subtask
        4. Collect all AgentResponses
        5. Synthesize with a final LLM call
        """
        self.log.info("jack received task", task=task.title)

        # Stub: direct LLM call as placeholder
        from skellington.core.types import Message, MessageRole

        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please orchestrate a response to this request:\n\n{task.description}",
            )
        ]

        return await self.chat(messages)
