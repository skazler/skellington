"""Integration tests for Zero.run() — Phase 3 (direct) and Phase 3.5 (orthodox MCP)."""

from __future__ import annotations

import json

import pytest

from skellington.agents.zero import Zero
from skellington.core.types import AgentName, Task, WorkflowState
from skellington.mcp_servers.filesystem.client import MCPFilesystemToolkit
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_zero_navigates_a_tiny_repo(allowed_tmp_path):
    # Build a minimal "repo" under the allowed tmp path
    (allowed_tmp_path / "main.py").write_text("import os\nimport mypkg.util\n")
    pkg = allowed_tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "util.py").write_text("def helper(): pass\n")
    (allowed_tmp_path / "README.md").write_text("# hello")

    # Every LLM call (tree summary, dep summary, context selection, synthesis)
    # returns the same canned response. The selection JSON is what ContextSubagent expects;
    # other callers just get the string content.
    main_path = str(allowed_tmp_path / "main.py").replace(chr(92), "/")
    canned_json = f'{{"files": [{{"path": "{main_path}", "reason": "entry"}}]}}'
    llm = make_mock_llm(canned_json)

    zero = Zero(llm_client=llm)

    task = Task(
        title="explore",
        description="Explore this repo",
        context={"path": str(allowed_tmp_path)},
    )
    state = WorkflowState(user_request="explore this repo")

    response = await zero.run(task, state)

    assert response.agent == AgentName.ZERO
    assert response.success is True
    assert response.metadata["total_files"] >= 3
    assert response.metadata["target_path"] == str(allowed_tmp_path)
    assert response.metadata["context_files_selected"] == 1

    # Navigation metadata should be published to the workflow state
    nav = state.metadata["navigation"][str(allowed_tmp_path)]
    assert nav["relevant_files"][0].endswith("main.py")


@pytest.mark.asyncio
async def test_zero_defaults_to_cwd_when_no_path_in_context(allowed_tmp_path, monkeypatch):
    """If task.context has no 'path', Zero uses '.' — which must resolve under allowed roots."""
    monkeypatch.chdir(allowed_tmp_path)
    (allowed_tmp_path / "only.py").write_text("x = 1")

    llm = make_mock_llm('{"files": []}')
    zero = Zero(llm_client=llm)
    task = Task(title="t", description="describe the current directory")
    state = WorkflowState(user_request="t")

    response = await zero.run(task, state)
    assert response.metadata["target_path"] == "."
    assert response.metadata["total_files"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_zero_navigates_through_orthodox_mcp(tmp_path, monkeypatch):
    """Phase 3.5 smoke test: Zero walks a repo via the real stdio MCP client."""
    monkeypatch.setenv("FILESYSTEM_ALLOWED_PATHS", json.dumps([str(tmp_path)]))

    # Build a tiny repo
    (tmp_path / "main.py").write_text("import os\nimport mypkg.util\n")
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "util.py").write_text("def helper(): pass\n")
    (tmp_path / "README.md").write_text("# hello")

    main_path = str(tmp_path / "main.py").replace(chr(92), "/")
    canned_json = f'{{"files": [{{"path": "{main_path}", "reason": "entry"}}]}}'
    llm = make_mock_llm(canned_json)

    task = Task(
        title="explore via mcp",
        description="Explore this repo through MCP",
        context={"path": str(tmp_path)},
    )
    state = WorkflowState(user_request="explore via mcp")

    async with MCPFilesystemToolkit() as fs:
        zero = Zero(llm_client=llm, fs=fs)
        response = await zero.run(task, state)

    assert response.agent == AgentName.ZERO
    assert response.success is True
    assert response.metadata["total_files"] >= 3
    assert response.metadata["context_files_selected"] == 1
    nav = state.metadata["navigation"][str(tmp_path)]
    assert nav["relevant_files"][0].endswith("main.py")
