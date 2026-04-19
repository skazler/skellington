"""WebSocket smoke test — ensures the /ws/run endpoint streams events.

We stub out Jack so we don't need real LLM calls; the test verifies that
the orchestrator's event bus is wired through to the WebSocket client.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_stub_jack(monkeypatch):
    """Replace Orchestrator.run with a stub that emits a scripted event sequence."""
    from skellington.core.orchestrator import Orchestrator
    from skellington.core.types import Task, TaskStatus, WorkflowState

    async def stub_run(self, user_request: str) -> WorkflowState:
        state = WorkflowState(user_request=user_request)
        root = Task(title="root", description=user_request, status=TaskStatus.COMPLETE, result="done")
        state.add_task(root)

        await self.emit("workflow.start", message=user_request)
        await self.emit("plan.created", message="2 steps", steps=["a", "b"])
        await self.emit("agent.start", agent="sally", message="a")
        await self.emit("agent.complete", agent="sally", message="built a", success=True)
        await self.emit("workflow.complete", message="done", success=True, task_count=1)
        return state

    monkeypatch.setattr(Orchestrator, "run", stub_run)

    from skellington.ui.web.app import app
    return app


def test_websocket_streams_events(app_with_stub_jack):
    client = TestClient(app_with_stub_jack)
    with client.websocket_connect("/ws/run") as ws:
        ws.send_json({"request": "hello"})

        received: list[dict] = []
        # Stub emits 5 events + the endpoint emits a result.final at the end.
        for _ in range(6):
            received.append(ws.receive_json())

    types = [e["type"] for e in received]
    assert types == [
        "workflow.start",
        "plan.created",
        "agent.start",
        "agent.complete",
        "workflow.complete",
        "result.final",
    ]

    plan_event = received[1]
    assert plan_event["data"]["steps"] == ["a", "b"]

    agent_start = received[2]
    assert agent_start["agent"] == "sally"
    assert agent_start["message"] == "a"

    final = received[5]
    assert final["message"] == "done"
    assert final["data"]["success"] is True
