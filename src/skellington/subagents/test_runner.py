"""
TestSubagent — test generation and coverage analysis.

Parent: Shock (Validator)
Learning goal: MCP code execution server for running actual tests.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class TestReport(BaseModel):
    passed: bool
    score: float
    suggested_tests: list[str]
    coverage_estimate: float
    missing_test_cases: list[str]


class TestSubagent(BaseSubAgent[TestReport]):
    """Analyzes test coverage and generates missing tests."""

    name = "test_runner"
    parent_agent = AgentName.SHOCK
    emoji = "🧪"
    description = "Test coverage analysis and test generation"

    @property
    def system_prompt(self) -> str:
        return """You are a testing expert. Analyze code for test coverage gaps and suggest tests.
TODO: Connect to code_exec MCP server to actually run tests.
Respond with JSON: {"passed": bool, "score": float (0-1),
"suggested_tests": [str], "coverage_estimate": float (0-1), "missing_test_cases": [str]}"""

    async def run(self, code: str) -> TestReport:
        """Analyze and report on test coverage."""
        response = await self._call_llm(f"Analyze test coverage for:\n\n{code}", temperature=0.2)
        import json

        data = json.loads(response)
        return TestReport(**data)
