"""
Base Agent class for Skellington.

Learning goal: How to define a clean agent interface that all characters
implement. Key patterns: abstract methods, tool registration, the
observe-think-act loop.
"""

from __future__ import annotations

import abc
import inspect
from collections.abc import Callable
from typing import Any

import structlog

from skellington.core.config import get_settings
from skellington.core.llm import LLMClient, LLMClientFactory
from skellington.core.models import get_model_card
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
from skellington.prompts import assemble_prompt

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
        self._model_card = get_model_card(self._model)
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
        description: str | None = None,
    ) -> None:
        """
        Register a callable tool that the LLM can invoke.

        Args:
            name: Tool name
            func: Async callable that implements the tool
            schema: JSON Schema for the tool's arguments — the `input_schema`
                half of a tool definition, not a whole definition. Every skill
                in this repo exports one of these. A complete definition
                (anything carrying `input_schema`) is passed through unchanged.
            description: What the tool does. Defaults to the first line of
                `func`'s docstring, which is where every skill already
                explains itself.
        """
        self._tools[name] = func

        if "input_schema" in schema:
            definition = schema
        else:
            # A bare JSON Schema has type "object" at the top level. Sent as a
            # tool definition, the API reads that as the tool's discriminator
            # and rejects the request.
            summary = description or (inspect.getdoc(func) or "").strip().split("\n")[0]
            definition = {
                "name": name,
                "description": summary or name,
                "input_schema": schema,
            }

        self._tool_schemas.append(definition)
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
        """Build an LLMConfig for this agent, with system prompt adapted to the model."""
        return LLMConfig(
            provider=self._llm.provider,
            model=self._model,
            system_prompt=assemble_prompt(self.system_prompt, self._model_card),
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
