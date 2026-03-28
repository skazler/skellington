"""Tests for Jack Skellington (Orchestrator)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.agents.jack import Jack
from skellington.core.types import AgentName, AgentResponse, Task, WorkflowState


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.provider = MagicMock()
    llm.complete = AsyncMock(
        return_value=MagicMock(
            content="I shall orchestrate this grand Christmas adventure!",
            tool_calls=[],
            model="test-model",
            input_tokens=10,
            output_tokens=20,
        )
    )
    return llm


@pytest.fixture
def jack(mock_llm):
    return Jack(llm_client=mock_llm)


def test_jack_name(jack):
    assert jack.name == AgentName.JACK


def test_jack_emoji(jack):
    assert "🎃" in jack.emoji


def test_jack_system_prompt(jack):
    prompt = jack.system_prompt
    assert "orchestrat" in prompt.lower()
    assert "Sally" in prompt or "sally" in prompt.lower()


@pytest.mark.asyncio
async def test_jack_run(jack):
    task = Task(title="Test", description="Do a thing")
    state = WorkflowState(user_request="Do a thing")
    response = await jack.run(task, state)
    assert isinstance(response, AgentResponse)
    assert response.agent == AgentName.JACK
    assert len(response.content) > 0
