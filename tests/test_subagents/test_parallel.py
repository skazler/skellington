"""Tests for parallel subagent execution."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.core.subagent import BaseSubAgent, run_subagents_parallel
from skellington.core.types import AgentName


class _EchoSubagent(BaseSubAgent[str]):
    name = "echo"
    parent_agent = AgentName.JACK

    @property
    def system_prompt(self) -> str:
        return "Echo agent"

    async def run(self, value: str, delay: float = 0.0) -> str:
        if delay:
            await asyncio.sleep(delay)
        return f"echo:{value}"


@pytest.mark.asyncio
async def test_run_subagents_parallel_ordering():
    a = _EchoSubagent(llm_client=MagicMock())
    b = _EchoSubagent(llm_client=MagicMock())
    c = _EchoSubagent(llm_client=MagicMock())

    results = await run_subagents_parallel(
        [
            (a, ("alpha",), {}),
            (b, ("beta",), {}),
            (c, ("gamma",), {}),
        ]
    )

    assert results == ["echo:alpha", "echo:beta", "echo:gamma"]


@pytest.mark.asyncio
async def test_run_subagents_parallel_exception_isolation():
    """An exception in one subagent should not crash the others."""

    class _FailingSubagent(BaseSubAgent[str]):
        name = "fail"
        parent_agent = AgentName.JACK

        @property
        def system_prompt(self) -> str:
            return ""

        async def run(self) -> str:
            raise ValueError("boom")

    good = _EchoSubagent(llm_client=MagicMock())
    bad = _FailingSubagent(llm_client=MagicMock())

    results = await run_subagents_parallel(
        [
            (good, ("ok",), {}),
            (bad, (), {}),
        ]
    )

    assert results[0] == "echo:ok"
    assert isinstance(results[1], ValueError)
