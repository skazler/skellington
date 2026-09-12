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

from skellington.agents import default_agents
from skellington.core.orchestrator import Orchestrator

app = FastAPI(
    title="Skellington",
    description="🎃 Multi-agent AI orchestration with Halloween-ized Christmas characters",
    version="0.1.0",
)


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

    orchestrator = Orchestrator(agents=default_agents())
    state = await orchestrator.run(request)

    return {
        "success": state.succeeded,
        "result": state.final_output,
        "error": state.error,
        "task_count": len(state.tasks),
    }


@app.websocket("/ws/run")
async def websocket_run(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming agent output in real time.

    Learning goal: WebSocket streaming with FastAPI — the orchestrator emits
    structured events (workflow.*, plan.*, route.*, agent.*, synthesis.*) and
    we forward each one as JSON to the browser so the UI can render a live
    timeline of what the crew is doing.
    """
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        request = data.get("request", "")

        async def forward(event: dict) -> None:
            try:
                await websocket.send_json(event)
            except Exception:  # noqa: BLE001 — client gone; let the workflow finish
                pass

        orchestrator = Orchestrator(agents=default_agents(), on_event=forward)
        state = await orchestrator.run(request)

        await websocket.send_json(
            {
                "type": "result.final",
                "agent": "jack",
                "message": state.final_output or "",
                "data": {
                    "success": state.succeeded,
                    "task_count": len(state.tasks),
                },
            }
        )
    except WebSocketDisconnect:
        pass
