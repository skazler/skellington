"""Tests for DependencySubagent."""

from __future__ import annotations

import pytest

from skellington.subagents.dependency import DependencySubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_dependency_extracts_internal_and_external_imports(allowed_tmp_path):
    pkg = allowed_tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("import os\nfrom mypkg.b import foo\n")
    (pkg / "b.py").write_text("import json\n")

    subagent = DependencySubagent(llm_client=make_mock_llm("dep summary"))
    graph = await subagent.run(str(allowed_tmp_path))

    assert "os" in graph.external_packages
    assert "json" in graph.external_packages
    # Internal edge a -> mypkg.b
    assert any(e["to"].startswith("mypkg.b") for e in graph.edges)
    assert graph.summary == "dep summary"


@pytest.mark.asyncio
async def test_dependency_handles_empty_directory(allowed_tmp_path):
    subagent = DependencySubagent(llm_client=make_mock_llm("unused"))
    graph = await subagent.run(str(allowed_tmp_path))

    assert graph.modules == []
    assert graph.edges == []
    assert graph.external_packages == []
    # With no edges we don't call the LLM — summary is the deterministic fallback
    assert "No Python import edges" in graph.summary


@pytest.mark.asyncio
async def test_dependency_detects_entry_points(allowed_tmp_path):
    (allowed_tmp_path / "main.py").write_text("import sys\n")
    (allowed_tmp_path / "other.py").write_text("import os\n")

    subagent = DependencySubagent(llm_client=make_mock_llm("summary"))
    graph = await subagent.run(str(allowed_tmp_path))

    assert any(ep.endswith("main.py") for ep in graph.entry_points)
    assert not any(ep.endswith("other.py") for ep in graph.entry_points)
