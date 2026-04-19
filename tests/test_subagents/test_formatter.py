"""Tests for FormatSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.formatter import FormattedOutput, FormatSubagent
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_formatter_parses_llm_json():
    payload = {
        "format": "markdown",
        "content": "# Hello\n\nWorld.",
        "title": "Greeting",
    }
    subagent = FormatSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    output = await subagent.run("hello world", target_format="markdown")

    assert isinstance(output, FormattedOutput)
    assert output.format == "markdown"
    assert output.title == "Greeting"


@pytest.mark.asyncio
async def test_formatter_defaults_when_fields_missing():
    subagent = FormatSubagent(llm_client=make_mock_llm('{"content": "rendered"}'))
    output = await subagent.run("raw input", target_format="html", title="My Page")

    assert output.format == "html"  # falls back to the requested format
    assert output.content == "rendered"
    assert output.title == "My Page"
