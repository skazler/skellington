"""
Base SubAgent class for Skellington.

Learning goal: Subagents are focused, single-purpose LLM calls that parent
agents delegate to. They differ from main agents in that:

1. They are spawned BY an agent for a specific subtask
2. They typically don't have their own tool-call loops
3. They return structured results back to the parent
4. They can run in PARALLEL for performance

Key patterns demonstrated here:
- SubAgent as a specialized, narrowly-scoped LLM call
- Structured output via Pydantic
- Parallel subagent execution with asyncio.gather
"""

from __future__ import annotations

import abc
import asyncio
from typing import Any, Generic, TypeVar

import structlog

from skellington.core.config import get_settings
from skellington.core.llm import LLMClient, LLMClientFactory
from skellington.core.types import (
    AgentName,
    LLMConfig,
    LLMProvider,
    Message,
    MessageRole,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")  # The structured output type


class BaseSubAgent(abc.ABC, Generic[T]):
    """
    Abstract base class for all Skellington subagents.

    SubAgents are lightweight, focused workers. They:
    - Receive a specific input
    - Run a focused LLM call
    - Return a structured result of type T

    Example usage:
        class SummarySubAgent(BaseSubAgent[SummaryResult]):
            async def run(self, text: str) -> SummaryResult:
                ...
    """

    # Override in subclasses
    name: str = "base_subagent"
    parent_agent: AgentName
    description: str = "A focused subagent"
    emoji: str = "👾"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        settings = get_settings()
        self._llm = llm_client or LLMClientFactory.create(provider)
        self._model = settings.get_model_for_agent(self.parent_agent.value)
        self.log = logger.bind(subagent=self.name, parent=self.parent_agent.value)

    @property
    @abc.abstractmethod
    def system_prompt(self) -> str:
        """The subagent's focused system prompt."""
        ...

    @abc.abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> T:
        """Execute this subagent's specific task and return a structured result."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _call_llm(self, user_message: str, temperature: float = 0.3) -> str:
        """
        Make a simple single-turn LLM call.

        SubAgents generally don't need tool-use loops — they just need
        a focused, well-prompted LLM call.
        """
        messages = [Message(role=MessageRole.USER, content=user_message)]
        config = LLMConfig(
            provider=self._llm.provider,
            model=self._model,
            system_prompt=self.system_prompt,
            temperature=temperature,
        )
        response = await self._llm.complete(messages, config)
        return response.content

    def __repr__(self) -> str:
        return f"{self.emoji} {self.__class__.__name__}(parent={self.parent_agent.value!r})"


# ---------------------------------------------------------------------------
# Parallel execution utility
# ---------------------------------------------------------------------------


async def run_subagents_parallel(
    subagents_and_inputs: list[tuple[BaseSubAgent, tuple, dict]],
) -> list[Any]:
    """
    Run multiple subagents concurrently using asyncio.gather.

    Learning goal: Parallel subagent execution for performance.
    Instead of running Lock → Shock → Barrel sequentially (3x slower),
    we run them all at once.

    Args:
        subagents_and_inputs: List of (subagent, args, kwargs) tuples

    Returns:
        List of results in the same order as inputs

    Example:
        results = await run_subagents_parallel([
            (lock_agent, (code,), {}),
            (shock_agent, (code,), {}),
            (barrel_agent, (code,), {}),
        ])
    """
    tasks = [subagent.run(*args, **kwargs) for subagent, args, kwargs in subagents_and_inputs]
    return await asyncio.gather(*tasks, return_exceptions=True)
