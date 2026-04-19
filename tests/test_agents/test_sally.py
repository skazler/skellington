"""Integration tests for Sally.run() — Phase 4 (direct) and Phase 4.5 (orthodox MCP)."""

from __future__ import annotations

import json

import pytest

from skellington.agents.sally import Sally
from skellington.core.types import AgentName, Task, WorkflowState
from skellington.mcp_servers.filesystem.client import MCPFilesystemToolkit
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_sally_generates_and_writes_a_single_file(allowed_tmp_path):
    payload = {
        "filename": "wordcount.py",
        "language": "python",
        "code": "def count(text: str) -> int:\n    return len(text.split())\n",
        "explanation": "word counter",
    }
    sally = Sally(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="wordcount",
        description="write a function that counts words in a string",
        context={"path": str(allowed_tmp_path)},
    )
    state = WorkflowState(user_request=task.description)

    response = await sally.run(task, state)

    assert response.agent == AgentName.SALLY
    assert response.success is True
    assert response.metadata["intent"] == "codegen"
    assert response.metadata["file_count"] == 1

    written = response.metadata["files_written"][0]
    assert written.endswith("wordcount.py")
    assert (allowed_tmp_path / "wordcount.py").read_text().startswith("def count(")

    # Build metadata is published for downstream consumers.
    build = state.metadata["builds"][str(task.id)]
    assert build["intent"] == "codegen"
    assert build["files_written"] == response.metadata["files_written"]


@pytest.mark.asyncio
async def test_sally_scaffolds_a_project(allowed_tmp_path):
    payload = {
        "project_name": "tiny_app",
        "files": {
            "src/tiny_app/__init__.py": "",
            "src/tiny_app/main.py": "print('hi')\n",
            "README.md": "# tiny_app",
        },
        "setup_commands": ["pip install -e ."],
    }
    sally = Sally(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="scaffold tiny_app",
        description="scaffold a new project called tiny_app that prints hi",
        context={"path": str(allowed_tmp_path)},
    )
    state = WorkflowState(user_request=task.description)

    response = await sally.run(task, state)

    assert response.metadata["intent"] == "scaffold"
    assert response.metadata["file_count"] == 3
    project_root = allowed_tmp_path / "tiny_app"
    assert (project_root / "src" / "tiny_app" / "main.py").read_text() == "print('hi')\n"
    assert (project_root / "README.md").exists()


@pytest.mark.asyncio
async def test_sally_refactors_inline_code(allowed_tmp_path):
    payload = {
        "code": "def add(a: int, b: int) -> int:\n    return a + b\n",
        "changes_made": ["added types"],
        "behavior_preserved": True,
    }
    sally = Sally(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="refactor add",
        description="refactor this code",
        context={"path": str(allowed_tmp_path), "code": "def add(a,b):\n    return a+b\n"},
    )
    state = WorkflowState(user_request=task.description)

    response = await sally.run(task, state)

    assert response.metadata["intent"] == "refactor"
    assert response.metadata["file_count"] == 1
    assert (allowed_tmp_path / "refactored.py").read_text().startswith("def add(a: int")


@pytest.mark.asyncio
async def test_sally_refactors_file_in_place(allowed_tmp_path):
    original = allowed_tmp_path / "old.py"
    original.write_text("def add(a,b):\n    return a+b\n")

    payload = {
        "code": "def add(a: int, b: int) -> int:\n    return a + b\n",
        "changes_made": ["added types"],
        "behavior_preserved": True,
    }
    sally = Sally(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="refactor old.py",
        description="refactor this code for clarity",
        context={"path": str(allowed_tmp_path), "file": str(original)},
    )
    state = WorkflowState(user_request=task.description)

    response = await sally.run(task, state)

    assert response.metadata["files_written"][0].endswith("old.py")
    assert original.read_text().startswith("def add(a: int")


@pytest.mark.asyncio
async def test_sally_defaults_to_codegen_for_generic_request(allowed_tmp_path):
    payload = {
        "filename": "output.py",
        "language": "python",
        "code": "x = 1\n",
        "explanation": "stub",
    }
    sally = Sally(llm_client=make_mock_llm(json.dumps(payload)))

    task = Task(
        title="write something",
        description="write a thing",
        context={"path": str(allowed_tmp_path)},
    )
    state = WorkflowState(user_request=task.description)

    response = await sally.run(task, state)
    assert response.metadata["intent"] == "codegen"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sally_builds_through_orthodox_mcp(tmp_path, monkeypatch):
    """Phase 4.5 smoke test: Sally writes real files via the stdio MCP client."""
    monkeypatch.setenv("FILESYSTEM_ALLOWED_PATHS", json.dumps([str(tmp_path)]))

    payload = {
        "filename": "wordcount.py",
        "language": "python",
        "code": "def count(t: str) -> int:\n    return len(t.split())\n",
        "explanation": "count words",
    }
    llm = make_mock_llm(json.dumps(payload))

    task = Task(
        title="wordcount via mcp",
        description="write a function that counts words",
        context={"path": str(tmp_path)},
    )
    state = WorkflowState(user_request=task.description)

    async with MCPFilesystemToolkit() as fs:
        sally = Sally(llm_client=llm, fs=fs)
        response = await sally.run(task, state)

    assert response.success is True
    assert response.metadata["intent"] == "codegen"
    assert (tmp_path / "wordcount.py").read_text().startswith("def count(")
