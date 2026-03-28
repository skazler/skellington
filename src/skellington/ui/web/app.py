"""
Skellington Web UI — FastAPI application.

Learning goal: Serving agent output via WebSockets for real-time streaming,
and building a REST API around the agent system.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from skellington.core.orchestrator import AgentRegistry, Orchestrator
from skellington.agents import Jack, Sally, Oogie, Zero, Mayor

app = FastAPI(
    title="Skellington",
    description="🎃 Multi-agent AI orchestration with Halloween-ized Christmas characters",
    version="0.1.0",
)


# Register agents on startup
@app.on_event("startup")
async def startup() -> None:
    for agent_class in [Jack, Sally, Oogie, Zero, Mayor]:
        AgentRegistry.register(agent_class())


# Static files & templates
_ui_dir = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_ui_dir / "templates"))

if (_ui_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=str(_ui_dir / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the main web UI."""
    return _templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/agents")
async def list_agents() -> dict:
    """Return available agent metadata."""
    return {
        "agents": [
            {"name": "jack", "emoji": "🎃👔", "role": "Orchestrator"},
            {"name": "sally", "emoji": "🧟‍♀️🎁", "role": "Builder"},
            {"name": "oogie", "emoji": "🎰🎅", "role": "Researcher"},
            {"name": "zero", "emoji": "👻🔴", "role": "Navigator"},
            {"name": "lock", "emoji": "👹", "role": "Validator"},
            {"name": "shock", "emoji": "🔮👹", "role": "Validator"},
            {"name": "barrel", "emoji": "💀👹", "role": "Validator"},
            {"name": "mayor", "emoji": "🎭📊", "role": "Reporter"},
        ]
    }


@app.post("/api/run")
async def run_request(body: dict) -> dict:
    """Execute a user request synchronously and return the result."""
    request = body.get("request", "")
    if not request:
        return {"error": "request is required"}

    orchestrator = Orchestrator()
    state = await orchestrator.run(request)

    root_task = state.tasks[0] if state.tasks else None
    return {
        "success": root_task.status.value == "complete" if root_task else False,
        "result": root_task.result if root_task else None,
        "error": root_task.error if root_task else "No tasks created",
        "task_count": len(state.tasks),
    }


@app.websocket("/ws/run")
async def websocket_run(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming agent output in real time.

    Learning goal: WebSocket streaming with FastAPI — connect the frontend
    to live agent updates as they happen.
    """
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        request = data.get("request", "")

        await websocket.send_json({"type": "status", "message": "🎃 Jack is on the case..."})

        orchestrator = Orchestrator()
        state = await orchestrator.run(request)

        root_task = state.tasks[0] if state.tasks else None
        await websocket.send_json(
            {
                "type": "complete",
                "success": root_task.status.value == "complete" if root_task else False,
                "result": root_task.result if root_task else None,
            }
        )
    except WebSocketDisconnect:
        pass
