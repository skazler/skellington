"""
TestSubagent — test generation and coverage analysis.

Parent: Shock (Validator)

The subagent itself is pure structured output — it looks at the code and
proposes tests / coverage estimates. Actually *running* pytest belongs to the
parent (Shock), which can route through the `code_exec` MCP server when it
wants real verification.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.utils.json_utils import extract_json


class TestReport(BaseModel):
    passed: bool
    score: float
    suggested_tests: list[str]
    coverage_estimate: float
    missing_test_cases: list[str]


class TestSubagent(BaseSubAgent[TestReport]):
    """Analyzes test coverage and suggests missing tests."""

    name = "test_runner"
    parent_agent = AgentName.SHOCK
    emoji = "🧪"
    description = "Test coverage analysis and test generation"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        fs=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._fs = fs

    @property
    def system_prompt(self) -> str:
        return """You are a testing expert. Analyze code for coverage gaps and suggest
concrete test cases that would catch bugs. Consider edge cases, error paths,
and behavioural boundaries.

Respond with ONLY a JSON object — no prose, no fences:
{"passed": bool, "score": float (0-1),
 "suggested_tests": [str],
 "coverage_estimate": float (0-1),
 "missing_test_cases": [str]}"""

    async def run(self, code: str) -> TestReport:
        """Analyze and report on test coverage."""
        response = await self._call_llm(f"Analyze test coverage for:\n\n{code}", temperature=0.2)
        data = extract_json(response)
        data.setdefault("passed", True)
        data.setdefault("score", 1.0)
        data.setdefault("suggested_tests", [])
        data.setdefault("coverage_estimate", 0.0)
        data.setdefault("missing_test_cases", [])
        return TestReport(**data)
