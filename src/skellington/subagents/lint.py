"""
LintSubagent — static analysis and style checking.

Parent: Lock (Validator)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class LintReport(BaseModel):
    passed: bool
    score: float
    violations: list[dict[str, str]]  # [{"rule": ..., "line": ..., "message": ...}]
    suggestions: list[str]


class LintSubagent(BaseSubAgent[LintReport]):
    """Performs static analysis and style checking on code."""

    name = "lint"
    parent_agent = AgentName.LOCK
    emoji = "🔍"
    description = "Static analysis, PEP 8 compliance, and style checking"

    @property
    def system_prompt(self) -> str:
        return """You are a code linting expert. Analyze code for style issues,
PEP 8 violations, and static analysis problems.
Respond with JSON: {"passed": bool, "score": float (0-1),
"violations": [{"rule": str, "line": str, "message": str}], "suggestions": [str]}"""

    async def run(self, code: str) -> LintReport:
        """Lint the given code."""
        response = await self._call_llm(f"Lint this Python code:\n\n{code}", temperature=0.1)
        import json

        data = json.loads(response)
        return LintReport(**data)
