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

from typing import Any, Awaitable, Callable

import structlog

from skellington.core.types import (
    AgentName,
    AgentResponse,
    Task,
    TaskStatus,
    WorkflowState,
)

logger = structlog.get_logger(__name__)


# An async event sink — the web UI passes a callback that pushes each event
# to a WebSocket; tests pass a list-appender. Sync callbacks also work
# (we await whatever the call returns; non-coroutines are tolerated).
EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class AgentRegistry:
    """
    Registry of available agents.

    Agents register themselves here so the orchestrator can find them.
    This is a simple service locator — in production you might use
    dependency injection instead.
    """

    _agents: dict[AgentName, object] = {}

    @classmethod
    def register(cls, agent: object) -> None:
        """Register an agent instance."""
        cls._agents[agent.name] = agent  # type: ignore[attr-defined]
        logger.debug("agent registered", agent=agent.name.value)  # type: ignore[attr-defined]

    @classmethod
    def get(cls, name: AgentName) -> object | None:
        """Retrieve an agent by name."""
        return cls._agents.get(name)

    @classmethod
    def available(cls) -> list[AgentName]:
        """List all registered agents."""
        return list(cls._agents.keys())


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

    def __init__(self, on_event: EventCallback | None = None) -> None:
        self.log = logger.bind(component="orchestrator")
        self._on_event = on_event

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
        self.log.info("starting workflow", request=user_request[:100])
        await self.emit("workflow.start", message=user_request)

        state = WorkflowState(user_request=user_request)

        # Create the root task
        root_task = Task(
            title="Handle user request",
            description=user_request,
            assigned_to=AgentName.JACK,
        )
        state.add_task(root_task)
        state.active_agent = AgentName.JACK

        # Get Jack and inject self so he can delegate back through us
        jack = AgentRegistry.get(AgentName.JACK)
        if jack is None:
            self.log.error("Jack not registered")
            root_task.status = TaskStatus.FAILED
            root_task.error = "Orchestrator: Jack (the orchestrator agent) is not registered"
            await self.emit("workflow.complete", message="Jack not registered", success=False)
            return state

        jack._orchestrator = self  # type: ignore[attr-defined]

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

        self.log.info("workflow complete", status=root_task.status.value)
        await self.emit(
            "workflow.complete",
            message=root_task.result or root_task.error or "",
            success=root_task.status == TaskStatus.COMPLETE,
            task_count=len(state.tasks),
        )
        return state

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
        agent = AgentRegistry.get(to_agent)
        if agent is None:
            return AgentResponse(
                agent=to_agent,
                task_id=task.id,
                content="",
                success=False,
                error=f"Agent '{to_agent.value}' is not registered",
            )

        task.assigned_to = to_agent
        task.status = TaskStatus.DELEGATED
        state.active_agent = to_agent

        self.log.info("delegating task", task=task.title, to=to_agent.value)
        await self.emit("agent.start", agent=to_agent, message=task.title)

        try:
            response = await agent.run(task, state)  # type: ignore[attr-defined]
            task.status = TaskStatus.COMPLETE if response.success else TaskStatus.FAILED
            task.result = response.content
            await self.emit(
                "agent.complete" if response.success else "agent.fail",
                agent=to_agent,
                message=(response.content or "")[:200],
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
