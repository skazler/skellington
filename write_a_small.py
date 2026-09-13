"""Small demo application built with Flask.

This module implements a minimal but production-quality Flask web
application that exposes a simple in-memory Task API. It demonstrates
core framework features such as routing, JSON request/response handling,
error handling, and application factory pattern.

Example:
    Run the app locally::

        $ python write_a_small.py

    Then interact with it::

        $ curl http://127.0.0.1:5000/
        $ curl -X POST http://127.0.0.1:5000/tasks \
            -H 'Content-Type: application/json' \
            -d '{"title": "Learn Flask"}'
        $ curl http://127.0.0.1:5000/tasks
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from flask import Flask, Response, jsonify, request
    from werkzeug.exceptions import HTTPException
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError(
        "Flask is required to run this demo. Install it with: pip install flask"
    ) from exc


logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a single task item.

    Attributes:
        id: Unique identifier assigned by the store.
        title: Human-readable task title.
        done: Whether the task has been completed.
        created_at: ISO 8601 UTC timestamp of creation.
    """

    id: int
    title: str
    done: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the task to a plain dictionary.

        Returns:
            A dictionary representation suitable for JSON encoding.
        """
        return asdict(self)


class TaskStore:
    """Thread-safe in-memory task storage.

    This class is intentionally simple and is only meant for the demo.
    In a real application you would use a persistent database instead.
    """

    def __init__(self) -> None:
        """Initialize an empty task store."""
        self._tasks: Dict[int, Task] = {}
        self._next_id: int = 1
        self._lock = threading.Lock()

    def list(self) -> List[Task]:
        """Return all stored tasks.

        Returns:
            A list of :class:`Task` objects ordered by insertion.
        """
        with self._lock:
            return list(self._tasks.values())

    def get(self, task_id: int) -> Optional[Task]:
        """Retrieve a task by its identifier.

        Args:
            task_id: The identifier to look up.

        Returns:
            The matching :class:`Task`, or ``None`` if not found.
        """
        with self._lock:
            return self._tasks.get(task_id)

    def add(self, title: str) -> Task:
        """Add a new task.

        Args:
            title: The title of the task. Must be a non-empty string.

        Returns:
            The newly created :class:`Task`.

        Raises:
            ValueError: If ``title`` is empty or not a string.
        """
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Task title must be a non-empty string.")
        with self._lock:
            task = Task(id=self._next_id, title=title.strip())
            self._tasks[task.id] = task
            self._next_id += 1
            return task

    def update(
        self,
        task_id: int,
        title: Optional[str] = None,
        done: Optional[bool] = None,
    ) -> Optional[Task]:
        """Update an existing task.

        Args:
            task_id: The identifier of the task to update.
            title: Optional new title.
            done: Optional new completion state.

        Returns:
            The updated :class:`Task`, or ``None`` if the task does
            not exist.

        Raises:
            ValueError: If provided fields have invalid types.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if title is not None:
                if not isinstance(title, str) or not title.strip():
                    raise ValueError("Task title must be a non-empty string.")
                task.title = title.strip()
            if done is not None:
                if not isinstance(done, bool):
                    raise ValueError("'done' must be a boolean.")
                task.done = done
            return task

    def delete(self, task_id: int) -> bool:
        """Delete a task.

        Args:
            task_id: The identifier of the task to remove.

        Returns:
            ``True`` if a task was removed, ``False`` otherwise.
        """
        with self._lock:
            return self._tasks.pop(task_id, None) is not None


def create_app(store: Optional[TaskStore] = None) -> Flask:
    """Application factory that wires the Flask app together.

    Args:
        store: Optional :class:`TaskStore` instance to inject. If not
            provided a fresh in-memory store is created.

    Returns:
        A configured :class:`flask.Flask` application instance.
    """
    app = Flask(__name__)
    task_store = store if store is not None else TaskStore()
    app.config["TASK_STORE"] = task_store

    @app.route("/", methods=["GET"])
    def index() -> Response:
        """Return API metadata and available endpoints."""
        return jsonify(
            {
                "name": "Task Demo API",
                "version": "1.0.0",
                "endpoints": {
                    "list_tasks": "GET /tasks",
                    "create_task": "POST /tasks",
                    "get_task": "GET /tasks/<id>",
                    "update_task": "PATCH /tasks/<id>",
                    "delete_task": "DELETE /tasks/<id>",
                    "health": "GET /health",
                },
            }
        )

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        """Simple liveness probe."""
        return jsonify({"status": "ok"})

    @app.route("/tasks", methods=["GET"])
    def list_tasks() -> Response:
        """List all tasks."""
        tasks = [t.to_dict() for t in task_store.list()]
        return jsonify({"tasks": tasks, "count": len(tasks)})

    @app.route("/tasks", methods=["POST"])
    def create_task() -> Tuple[Response, int]:
        """Create a new task from a JSON body containing ``title``."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "title" not in payload:
            return jsonify({"error": "JSON body with 'title' is required."}), 400
        try:
            task = task_store.add(str(payload["title"]))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        logger.info("Created task id=%s", task.id)
        return jsonify(task.to_dict()), 201

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id: int) -> Tuple[Response, int]:
        """Return a single task by id."""
        task = task_store.get(task_id)
        if task is None:
            return jsonify({"error": f"Task {task_id} not found."}), 404
        return jsonify(task.to_dict()), 200

    @app.route("/tasks/<int:task_id>", methods=["PATCH"])
    def update_task(task_id: int) -> Tuple[Response, int]:
        """Partially update a task."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body is required."}), 400
        try:
            task = task_store.update(
                task_id,
                title=payload.get("title"),
                done=payload.get("done"),
            )
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        if task is None:
            return jsonify({"error": f"Task {task_id} not found."}), 404
        return jsonify(task.to_dict()), 200

    @app.route("/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id: int) -> Tuple[Response, int]:
        """Delete a task by id."""
        if not task_store.delete(task_id):
            return jsonify({"error": f"Task {task_id} not found."}), 404
        return jsonify({"deleted": task_id}), 200

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException) -> Tuple[Response, int]:
        """Convert Werkzeug HTTP exceptions to JSON responses."""
        response = jsonify({"error": err.description, "code": err.code})
        return response, err.code or 500

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception) -> Tuple[Response, int]:
        """Catch-all handler to prevent HTML error pages leaking."""
        logger.exception("Unhandled server error: %s", err)
        return jsonify({"error": "Internal server error"}), 500

    return app


def main() -> None:
    """Entry point for running the demo app from the command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    host = os.environ.get("HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("PORT", "5000"))
    except ValueError as err:
        raise SystemExit(f"Invalid PORT environment variable: {err}") from err
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app = create_app()
    logger.info("Starting Task Demo API on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
