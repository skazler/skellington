"""FastAPI demo application showcasing a simple task management REST API.

This module implements a small but production-quality demo using FastAPI,
one of the most popular modern Python web frameworks. It demonstrates:

* Typed request/response models via Pydantic
* Full CRUD endpoints for a ``Task`` resource
* Proper HTTP status codes and error handling
* Structured logging
* An in-memory thread-safe repository (easily swappable for a real DB)

Run the demo with::

    uvicorn implement_the_demo:app --reload

Then visit http://127.0.0.1:8000/docs for the interactive Swagger UI.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger: logging.Logger = logging.getLogger("task_demo")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class TaskCreate(BaseModel):
    """Payload used to create a new task.

    Attributes:
        title: Short, human-readable title for the task.
        description: Optional longer description of the task.
        completed: Whether the task is already completed.
    """

    title: str = Field(..., min_length=1, max_length=200, examples=["Buy groceries"])
    description: Optional[str] = Field(
        default=None, max_length=2000, examples=["Milk, eggs, bread"]
    )
    completed: bool = Field(default=False)


class TaskUpdate(BaseModel):
    """Payload for partial updates to an existing task.

    All fields are optional; only provided fields will be modified.
    """

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    completed: Optional[bool] = None


class Task(TaskCreate):
    """A fully materialized task returned by the API.

    Attributes:
        id: Server-generated unique identifier.
        created_at: UTC timestamp when the task was created.
        updated_at: UTC timestamp when the task was last modified.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# In-memory repository
# ---------------------------------------------------------------------------
class TaskRepository:
    """Thread-safe in-memory storage for :class:`Task` objects.

    In a real application this would be backed by a database. The interface
    is intentionally small so it can be swapped with an async ORM or an
    external service without changing the API layer.
    """

    def __init__(self) -> None:
        self._tasks: Dict[UUID, Task] = {}
        self._lock: threading.Lock = threading.Lock()

    def list(self, completed: Optional[bool] = None) -> List[Task]:
        """Return all tasks, optionally filtered by completion state.

        Args:
            completed: If provided, only tasks matching this value are
                returned.

        Returns:
            A list of tasks ordered by creation time (oldest first).
        """
        with self._lock:
            tasks = list(self._tasks.values())
        if completed is not None:
            tasks = [t for t in tasks if t.completed == completed]
        return sorted(tasks, key=lambda t: t.created_at)

    def get(self, task_id: UUID) -> Task:
        """Fetch a single task by its identifier.

        Args:
            task_id: The task's UUID.

        Returns:
            The matching :class:`Task`.

        Raises:
            KeyError: If no task with the given id exists.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def create(self, payload: TaskCreate) -> Task:
        """Persist a new task.

        Args:
            payload: The user-supplied task data.

        Returns:
            The newly created :class:`Task`, including generated metadata.
        """
        now = datetime.now(timezone.utc)
        task = Task(
            id=uuid4(),
            title=payload.title,
            description=payload.description,
            completed=payload.completed,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task.id] = task
        logger.info("Created task %s", task.id)
        return task

    def update(self, task_id: UUID, payload: TaskUpdate) -> Task:
        """Apply a partial update to an existing task.

        Args:
            task_id: The task's UUID.
            payload: The fields to modify.

        Returns:
            The updated :class:`Task`.

        Raises:
            KeyError: If the task does not exist.
        """
        with self._lock:
            existing = self._tasks.get(task_id)
            if existing is None:
                raise KeyError(task_id)

            update_data = payload.model_dump(exclude_unset=True)
            updated = existing.model_copy(
                update={**update_data, "updated_at": datetime.now(timezone.utc)}
            )
            self._tasks[task_id] = updated
        logger.info("Updated task %s (fields=%s)", task_id, list(update_data))
        return updated

    def delete(self, task_id: UUID) -> None:
        """Remove a task from storage.

        Args:
            task_id: The task's UUID.

        Raises:
            KeyError: If the task does not exist.
        """
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            del self._tasks[task_id]
        logger.info("Deleted task %s", task_id)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app: FastAPI = FastAPI(
    title="Task Demo API",
    description="A minimal FastAPI demo implementing a task management service.",
    version="1.0.0",
)
repository: TaskRepository = TaskRepository()


@app.get("/health", tags=["system"])
def health_check() -> Dict[str, str]:
    """Return a basic liveness probe response.

    Returns:
        A dictionary reporting the service status.
    """
    return {"status": "ok"}


@app.get("/tasks", response_model=List[Task], tags=["tasks"])
def list_tasks(
    completed: Optional[bool] = Query(
        default=None, description="Filter by completion state."
    ),
) -> List[Task]:
    """List all tasks, optionally filtered by completion state."""
    return repository.list(completed=completed)


@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
def create_task(payload: TaskCreate) -> Task:
    """Create a new task."""
    return repository.create(payload)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(
    task_id: UUID = Path(..., description="Unique task identifier."),
) -> Task:
    """Fetch a specific task by ID."""
    try:
        return repository.get(task_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        ) from exc


@app.patch("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def update_task(
    payload: TaskUpdate,
    task_id: UUID = Path(..., description="Unique task identifier."),
) -> Task:
    """Partially update an existing task."""
    try:
        return repository.update(task_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        ) from exc


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tasks"],
)
def delete_task(
    task_id: UUID = Path(..., description="Unique task identifier."),
) -> None:
    """Delete a task by ID."""
    try:
        repository.delete(task_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        ) from exc


# ---------------------------------------------------------------------------
# Entrypoint for ``python implement_the_demo.py``
# ---------------------------------------------------------------------------
def main() -> None:
    """Run the demo using Uvicorn's programmatic API."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - defensive
        raise SystemExit(
            "Uvicorn is required to run this demo. Install it with `pip install uvicorn`."
        ) from exc

    uvicorn.run(
        "implement_the_demo:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
