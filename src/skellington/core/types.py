"""
Shared types and data models for Skellington.

Learning goal: Pydantic v2 for validated data models across the agent system.
All inter-agent communication flows through these types.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentName(StrEnum):
    """The Halloween-ized Christmas characters."""

    JACK = "jack"  # Orchestrator
    SALLY = "sally"  # Builder
    OOGIE = "oogie"  # Researcher
    ZERO = "zero"  # Navigator
    LOCK = "lock"  # Validator 1
    SHOCK = "shock"  # Validator 2
    BARREL = "barrel"  # Validator 3
    MAYOR = "mayor"  # Reporter


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LITELLM = "litellm"  # Catch-all via LiteLLM


class TaskStatus(StrEnum):
    """Lifecycle states for a task."""

    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    DELEGATED = "delegated"
    AWAITING_VALIDATION = "awaiting_validation"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(StrEnum):
    """Roles in an LLM conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ---------------------------------------------------------------------------
# Core Message Types
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single message in a conversation."""

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool invocation request from an LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """The result of a tool invocation."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


# ---------------------------------------------------------------------------
# Usage Accounting
# ---------------------------------------------------------------------------


class ModelUsage(BaseModel):
    """Tokens attributed to a single model id."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class Usage(BaseModel):
    """Token totals for a run, with a per-model breakdown.

    The breakdown is what makes the cheap-subagent levers (PLANNER_MODEL,
    ROUTER_MODEL) measurable rather than merely plausible.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_model: dict[str, ModelUsage] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def since(self, earlier: Usage) -> Usage:
        """Usage accumulated after `earlier` was snapshotted.

        Recorders outlive a single workflow, so a run reports its own delta
        rather than the recorder's running totals.
        """
        by_model: dict[str, ModelUsage] = {}
        for model, now in self.by_model.items():
            was = earlier.by_model.get(model, ModelUsage())
            delta = ModelUsage(
                calls=now.calls - was.calls,
                input_tokens=now.input_tokens - was.input_tokens,
                output_tokens=now.output_tokens - was.output_tokens,
            )
            if delta.calls:
                by_model[model] = delta
        return Usage(
            calls=self.calls - earlier.calls,
            input_tokens=self.input_tokens - earlier.input_tokens,
            output_tokens=self.output_tokens - earlier.output_tokens,
            by_model=by_model,
        )


# ---------------------------------------------------------------------------
# Task & Workflow Types
# ---------------------------------------------------------------------------


class Task(BaseModel):
    """A unit of work that can be assigned to an agent."""

    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: AgentName | None = None
    created_by: AgentName | None = None
    parent_task_id: UUID | None = None  # For subtask hierarchies
    subtask_ids: list[UUID] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentHandoff(BaseModel):
    """Data passed when Jack delegates to a specialist agent."""

    task: Task
    instructions: str
    context: dict[str, Any] = Field(default_factory=dict)
    return_to: AgentName = AgentName.JACK


class WorkflowState(BaseModel):
    """Complete state of an in-progress workflow."""

    id: UUID = Field(default_factory=uuid4)
    user_request: str
    tasks: list[Task] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    active_agent: AgentName | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
        self.updated_at = datetime.utcnow()

    def get_task(self, task_id: UUID) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    @property
    def root_task(self) -> Task | None:
        """The task the orchestrator created for the user's request."""
        return self.tasks[0] if self.tasks else None

    # The outcome lives on the root task; these derive it rather than storing
    # a second copy that can drift. computed_field keeps them in model_dump(),
    # so a serialized run still carries its answer.

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_output(self) -> str | None:
        """The answer to hand back to the user, or None if there isn't one."""
        root = self.root_task
        return root.result if root else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def succeeded(self) -> bool:
        """Whether the workflow reached a complete root task."""
        root = self.root_task
        return root is not None and root.status == TaskStatus.COMPLETE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error(self) -> str | None:
        """Why the workflow failed, or None if it didn't."""
        root = self.root_task
        return root.error if root else "No tasks created"


# ---------------------------------------------------------------------------
# Agent Response Types
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """Standardized response from any agent or subagent."""

    agent: AgentName
    task_id: UUID | None = None
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


class ValidationVerdict(BaseModel):
    """A single validator's verdict (Lock, Shock, or Barrel)."""

    validator: Literal[AgentName.LOCK, AgentName.SHOCK, AgentName.BARREL]
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    issues: list[str] = Field(default_factory=list)


class ConsensusResult(BaseModel):
    """Combined verdict from all three validators."""

    verdicts: list[ValidationVerdict]
    passed: bool
    average_score: float
    summary: str

    @classmethod
    def from_verdicts(cls, verdicts: list[ValidationVerdict]) -> ConsensusResult:
        passed_count = sum(1 for v in verdicts if v.passed)
        avg_score = sum(v.score for v in verdicts) / len(verdicts) if verdicts else 0.0
        passed = passed_count >= 2  # Majority rules
        summary = f"{passed_count}/{len(verdicts)} validators passed (avg score: {avg_score:.2f})"
        return cls(verdicts=verdicts, passed=passed, average_score=avg_score, summary=summary)


# ---------------------------------------------------------------------------
# LLM Configuration Types
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """Configuration for an LLM call."""

    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-opus-4-7"
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False
    # Opt-ins honored only when the model's ModelCard supports them.
    response_format: Literal["text", "json"] = "text"
    prefer_thinking: bool = False
    thinking_budget_tokens: int = 4096


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""

    content: str
    model: str
    provider: LLMProvider
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stop_reason: str = "end_turn"
