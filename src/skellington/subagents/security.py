"""
SecuritySubagent — vulnerability scanning and security analysis.

Parent: Barrel (Validator)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class SecurityReport(BaseModel):
    passed: bool
    score: float
    vulnerabilities: list[dict[str, str]]  # [{"severity": ..., "type": ..., "description": ...}]
    recommendations: list[str]


class SecuritySubagent(BaseSubAgent[SecurityReport]):
    """Scans code for security vulnerabilities."""

    name = "security"
    parent_agent = AgentName.BARREL
    emoji = "🔒"
    description = "Security vulnerability scanning and analysis"

    @property
    def system_prompt(self) -> str:
        return """You are a security expert. Scan code for vulnerabilities including:
SQL injection, XSS, authentication issues, insecure dependencies, data exposure.
Respond with JSON: {"passed": bool, "score": float (0-1),
"vulnerabilities": [{"severity": str, "type": str, "description": str}],
"recommendations": [str]}"""

    async def run(self, code: str) -> SecurityReport:
        """Perform a security analysis of the given code."""
        response = await self._call_llm(f"Security scan this code:\n\n{code}", temperature=0.1)
        import json

        data = json.loads(response)
        return SecurityReport(**data)
