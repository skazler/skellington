"""Tests for ScaffoldSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.scaffold import ScaffoldPlan, ScaffoldSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_scaffold_parses_multi_file_plan():
    payload = {
        "project_name": "wordcount",
        "files": {
            "src/wordcount/__init__.py": "",
            "src/wordcount/cli.py": "def main():\n    pass\n",
            "README.md": "# wordcount",
        },
        "setup_commands": ["pip install -e ."],
    }
    subagent = ScaffoldSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    plan = await subagent.run("build a word count CLI", project_name="wordcount")

    assert isinstance(plan, ScaffoldPlan)
    assert plan.project_name == "wordcount"
    assert "src/wordcount/cli.py" in plan.files
    assert plan.setup_commands == ["pip install -e ."]


@pytest.mark.asyncio
async def test_scaffold_fills_defaults_for_partial_llm_output():
    # LLM only returned files — missing project_name and setup_commands.
    partial = '{"files": {"a.py": "x = 1"}}'
    subagent = ScaffoldSubagent(llm_client=make_mock_llm(partial))
    plan = await subagent.run("anything", project_name="fallback_name")

    assert plan.project_name == "fallback_name"
    assert plan.files == {"a.py": "x = 1"}
    assert plan.setup_commands == []
