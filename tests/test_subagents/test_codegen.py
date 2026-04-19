"""Tests for CodeGenSubagent."""

from __future__ import annotations

import json

import pytest

from skellington.subagents.codegen import CodeGenSubagent, GeneratedCode
from tests.conftest import make_mock_llm


@pytest.mark.asyncio
async def test_codegen_parses_llm_json():
    payload = {
        "filename": "hello.py",
        "language": "python",
        "code": "print('hi')\n",
        "explanation": "tiny script",
    }
    subagent = CodeGenSubagent(llm_client=make_mock_llm(json.dumps(payload)))
    result = await subagent.run("print hi", filename="hello.py")

    assert isinstance(result, GeneratedCode)
    assert result.filename == "hello.py"
    assert result.code == "print('hi')\n"


@pytest.mark.asyncio
async def test_codegen_extracts_json_from_fenced_response():
    fenced = '```json\n{"filename":"x.py","language":"python","code":"x=1","explanation":"ok"}\n```'
    subagent = CodeGenSubagent(llm_client=make_mock_llm(fenced))
    result = await subagent.run("set x", filename="x.py")

    assert result.filename == "x.py"
    assert result.code == "x=1"


@pytest.mark.asyncio
async def test_codegen_falls_back_to_requested_filename_if_missing():
    # LLM forgot the filename field — subagent should fill it in from the argument.
    partial = '{"language":"python","code":"pass","explanation":"stub"}'
    subagent = CodeGenSubagent(llm_client=make_mock_llm(partial))
    result = await subagent.run("stub", filename="stub.py")

    assert result.filename == "stub.py"
