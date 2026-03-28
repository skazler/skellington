"""
Base Agent class for Skellington.

Learning goal: How to define a clean agent interface that all characters
implement. Key patterns: abstract methods, tool registration, the
observe-think-act loop.
"""

from __future__ import annotations

import abc
from typing import Any, Callable

import structlog

from skellington.core.config import get_settings
from skellington.core.llm import LLMClient, LLMClientFactory
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMConfig,
    LLMProvider,
    Message,
    MessageRole,
    Task,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


class BaseAgent(abc.ABC):
    """
    Abstract base class for all Skellington agents.

    Each character (Jack, Sally, Oogie, Zero, etc.) is a subclass of BaseAgent.
    Agents have:
      - A NAME (their character)
      - A SYSTEM PROMPT (their personality & instructions)
      - TOOLS they can call (via MCP or direct function)
      - An LLM client (swappable via config)

    The core loop: receive task → build messages → call LLM → handle tool calls
    → return AgentResponse.
    """

    # Override in each subclass
    name: AgentName
    emoji: str = "🎃"
    description: str = "A Skellington agent"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        settings = get_settings()
        self._llm = llm_client or LLMClientFactory.create(provider)
        self._model = settings.get_model_for_agent(self.name.value)
        self._tools: dict[str, Callable] = {}
        self._tool_schemas: list[dict[str, Any]] = []
        self.log = logger.bind(agent=self.name.value)

    # ------------------------------------------------------------------
    # Abstract interface — every agent must implement these
    # ------------------------------------------------------------------

    @property
    @abc.abstractmethod
    def system_prompt(self) -> str:
        """
        The agent's personality and operating instructions.

        This is where you define WHO the agent is and WHAT they do.
        Keep it focused — an agent that tries to do everything does nothing well.
        """
        ...

    @abc.abstractmethod
    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Execute a task and return a response.

        This is the main entry point. Implementations should:
        1. Build the message history
        2. Call the LLM (with tool use if needed)
        3. Handle any tool calls
        4. Return an AgentResponse
        """
        ...

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        func: Callable,
        schema: dict[str, Any],
    ) -> None:
        """
        Register a callable tool that the LLM can invoke.

        Args:
            name: Tool name (must match the schema name)
            func: Async callable that implements the tool
            schema: JSON schema dict in the provider's tool format
        """
        self._tools[name] = func
        self._tool_schemas.append(schema)
        self.log.debug("registered tool", tool=name)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a registered tool and return its string result."""
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"
        try:
            result = await self._tools[name](**arguments)
            return str(result)
        except Exception as exc:
            self.log.error("tool call failed", tool=name, error=str(exc))
            return f"Error calling tool '{name}': {exc}"

    # ------------------------------------------------------------------
    # LLM interaction helpers
    # ------------------------------------------------------------------

    def build_config(self, stream: bool = False) -> LLMConfig:
        """Build an LLMConfig for this agent."""
        return LLMConfig(
            provider=self._llm.provider,
            model=self._model,
            system_prompt=self.system_prompt,
            tools=self._tool_schemas,
            stream=stream,
        )

    async def chat(
        self,
        messages: list[Message],
        extra_context: str | None = None,
    ) -> AgentResponse:
        """
        Run a single chat turn (with automatic tool-call handling).

        This implements the observe → think → act loop:
        1. Optionally append extra context to the last user message
        2. Call the LLM
        3. If the LLM requests tool calls, execute them and loop
        4. Return the final response
        """
        if extra_context:
            messages = [
                *messages,
                Message(role=MessageRole.USER, content=extra_context),
            ]

        config = self.build_config()
        max_iterations = 10
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            llm_response = await self._llm.complete(messages, config)

            if not llm_response.tool_calls:
                # No more tool calls — we have our final answer
                return AgentResponse(
                    agent=self.name,
                    content=llm_response.content,
                    metadata={
                        "model": llm_response.model,
                        "input_tokens": llm_response.input_tokens,
                        "output_tokens": llm_response.output_tokens,
                        "iterations": iterations,
                    },
                )

            # Execute tool calls and continue the loop
            self.log.debug("handling tool calls", count=len(llm_response.tool_calls))
            tool_result_parts: list[str] = []

            for tool_call in llm_response.tool_calls:
                result = await self.call_tool(tool_call.name, tool_call.arguments)
                tool_result_parts.append(f"[{tool_call.name}]: {result}")

            # Add the assistant's tool-call turn + results to history
            messages = [
                *messages,
                Message(
                    role=MessageRole.ASSISTANT,
                    content=llm_response.content or "",
                ),
                Message(
                    role=MessageRole.USER,
                    content="\n".join(tool_result_parts),
                ),
            ]

        return AgentResponse(
            agent=self.name,
            content="[Exceeded maximum tool-call iterations]",
            success=False,
            error="max_iterations_exceeded",
        )

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"{self.emoji} {self.__class__.__name__}(name={self.name.value!r}, model={self._model!r})"
