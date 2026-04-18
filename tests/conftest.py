"""
Shared pytest fixtures for Skellington tests.

- `allowed_tmp_path`: a tmp directory with filesystem access control unlocked,
  so tests can exercise the real filesystem tools without touching real paths.
- `mock_llm`: a MagicMock LLM client configured enough to satisfy BaseAgent/BaseSubAgent.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skellington.core.types import LLMProvider


@pytest.fixture
def allowed_tmp_path(tmp_path):
    """Allow filesystem tools to read/write under `tmp_path` only."""
    with patch(
        "skellington.mcp_servers.filesystem.tools.get_settings",
        return_value=type("S", (), {"filesystem_allowed_paths": [str(tmp_path)]})(),
    ):
        yield tmp_path


def make_mock_llm(content: str = "ok") -> Any:
    """Build a MagicMock LLM client that returns a fixed completion string."""
    llm = MagicMock()
    llm.provider = LLMProvider.ANTHROPIC
    llm.complete = AsyncMock(
        return_value=MagicMock(
            content=content,
            tool_calls=[],
            model="test",
            input_tokens=5,
            output_tokens=5,
        )
    )
    return llm


@pytest.fixture
def mock_llm():
    """Default mock LLM that replies 'ok' to every call."""
    return make_mock_llm("ok")
