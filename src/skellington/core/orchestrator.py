"""
Workflow orchestrator — Jack's engine.

Learning goal: How orchestrators manage multi-agent workflows.
Key patterns:
- Task decomposition (one big task → many small tasks)
- Agent routing (which agent handles which task?)
- State management across an entire workflow
- Error recovery and retry logic
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import structlog

from skellington.core.types import (
    AgentName,
    AgentResponse,
    Task,
    TaskStatus,
    WorkflowState,
)
from skellington.core.usage import UsageRecorder

logger = structlog.get_logger(__name__)


# An async event sink — the web UI passes a callback that pushes each event
# to a WebSocket; tests pass a list-appender. Sync callbacks also work
# (we await whatever the call returns; non-coroutines are tolerated).
EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class Orchestrator:
    """
    Top-level workflow orchestrator.

    The Orchestrator is the engine that Jack runs on. It:
    1. Receives a user request
    2. Creates a WorkflowState to track everything
    3. Delegates to Jack (who then delegates to specialists)
    4. Monitors task completion
    5. Returns the final result

    Think of it as the stage manager behind Jack's performance.
    """

    def __init__(
        self,
        agents: Iterable[object] = (),
        on_event: EventCallback | None = None,
        usage: UsageRecorder | None = None,
        cache_workflows: bool = False,
        cache_size: int = 32,
    ) -> None:
        self.log = logger.bind(component="orchestrator")
        self._usage = usage
        self._agents: dict[AgentName, object] = {a.name: a for a in agents}  # type: ignore[attr-defined]
        self._on_event = on_event
        self._cache_enabled = cache_workflows
        self._cache_size = cache_size
        self._cache: OrderedDict[str, WorkflowState] = OrderedDict()

        # Jack delegates back through us, so he needs a reference. Wired once
        # here rather than on every run(): a shared Jack mutated per-run means
        # two orchestrators silently fight over the same instance.
        jack = self._agents.get(AgentName.JACK)
        if jack is not None:
            jack._orchestrator = self  # type: ignore[attr-defined]

    @property
    def agents(self) -> list[AgentName]:
        """Names of the agents this orchestrator can delegate to."""
        return list(self._agents)

    async def emit(
        self,
        event_type: str,
        *,
        agent: AgentName | str | None = None,
        message: str = "",
        **data: Any,
    ) -> None:
        """Forward a single workflow event to the registered callback (if any).

        Swallows callback errors so a broken UI never crashes the workflow.
        """
        if self._on_event is None:
            return
        agent_value = agent.value if isinstance(agent, AgentName) else agent
        event = {"type": event_type, "agent": agent_value, "message": message, "data": data}
        try:
            result = self._on_event(event)
            if result is not None:  # support both sync and async callbacks
                await result
        except Exception as exc:  # noqa: BLE001 — never let UI plumbing crash the workflow
            self.log.warning("event callback failed", error=str(exc), event_type=event_type)

    async def run(self, user_request: str) -> WorkflowState:
        """
        Execute a user request end-to-end.

        This is the main entry point for the entire system.
        """
        cache_key = self._cache_key(user_request) if self._cache_enabled else None
        if cache_key and cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            cached = self._cache[cache_key]
            self.log.info("workflow cache hit, returning prior result", request=user_request[:100])
            await self.emit("workflow.cache_hit", message=user_request)
            return cached

        self.log.info("starting workflow", request=user_request[:100])
        await self.emit("workflow.start", message=user_request)

        # Recorders are wired into the agents' LLM client and outlive any one
        # workflow, so a run reports the delta it is responsible for.
        usage_before = self._usage.snapshot() if self._usage else None

        state = WorkflowState(user_request=user_request)

        # Create the root task
        root_task = Task(
            title="Handle user request",
            description=user_request,
            assigned_to=AgentName.JACK,
        )
        state.add_task(root_task)
        state.active_agent = AgentName.JACK

        jack = self._agents.get(AgentName.JACK)
        if jack is None:
            self.log.error("Jack not registered")
            root_task.status = TaskStatus.FAILED
            root_task.error = "Orchestrator: Jack (the orchestrator agent) is not registered"
            # Same payload shape as the normal exit — consumers parse one event.
            await self.emit(
                "workflow.complete",
                message=root_task.error,
                success=False,
                task_count=len(state.tasks),
                usage=state.usage.model_dump(),
            )
            return state

        # Run Jack
        try:
            root_task.status = TaskStatus.IN_PROGRESS
            response: AgentResponse = await jack.run(root_task, state)  # type: ignore[attr-defined]
            root_task.result = response.content
            root_task.status = TaskStatus.COMPLETE if response.success else TaskStatus.FAILED
            if not response.success:
                root_task.error = response.error
        except Exception as exc:
            self.log.exception("workflow failed", error=str(exc))
            root_task.status = TaskStatus.FAILED
            root_task.error = str(exc)

        if self._usage is not None and usage_before is not None:
            state.usage = self._usage.snapshot().since(usage_before)

        self.log.info("workflow complete", status=root_task.status.value)
        await self.emit(
            "workflow.complete",
            message=root_task.result or root_task.error or "",
            success=root_task.status == TaskStatus.COMPLETE,
            task_count=len(state.tasks),
            usage=state.usage.model_dump(),
        )

        # Only cache successful workflows — caching failures would make a
        # transient error sticky.
        if cache_key and root_task.status == TaskStatus.COMPLETE:
            self._cache[cache_key] = state
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

        return state

    @staticmethod
    def _cache_key(user_request: str) -> str:
        """Stable hash of the user request. Whitespace-normalized to maximize hits."""
        normalized = " ".join(user_request.split()).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def delegate(
        self,
        task: Task,
        to_agent: AgentName,
        state: WorkflowState,
    ) -> AgentResponse:
        """
        Delegate a task to a specific agent.

        Called by Jack when routing subtasks to Sally, Oogie, Zero, etc.
        """
        task.assigned_to = to_agent
        task.status = TaskStatus.DELEGATED
        state.active_agent = to_agent

        self.log.info("delegating task", task=task.title, to=to_agent.value)
        await self.emit("agent.start", agent=to_agent, message=task.title)

        # Looked up after agent.start so that every delegation produces a
        # start plus exactly one terminal event. A missing agent that returned
        # early here would drop the step silently and still report success.
        agent = self._agents.get(to_agent)
        if agent is None:
            error = f"Agent '{to_agent.value}' is not registered"
            self.log.error("delegation target not registered", to=to_agent.value)
            task.status = TaskStatus.FAILED
            task.error = error
            await self.emit("agent.fail", agent=to_agent, message=error, success=False)
            return AgentResponse(
                agent=to_agent,
                task_id=task.id,
                content="",
                success=False,
                error=error,
            )

        try:
            response = await agent.run(task, state)  # type: ignore[attr-defined]
            task.status = TaskStatus.COMPLETE if response.success else TaskStatus.FAILED
            task.result = response.content
            if not response.success:
                task.error = response.error
            # A failed response carries its reason in .error, and usually has
            # empty .content — reporting content would say nothing at all.
            detail = response.content if response.success else (response.error or "")
            await self.emit(
                "agent.complete" if response.success else "agent.fail",
                agent=to_agent,
                message=(detail or "")[:200],
                success=response.success,
            )
            return response
        except Exception as exc:
            self.log.exception("delegated task failed", to=to_agent.value, error=str(exc))
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            await self.emit("agent.fail", agent=to_agent, message=str(exc), success=False)
            return AgentResponse(
                agent=to_agent,
                task_id=task.id,
                content="",
                success=False,
                error=str(exc),
            )
