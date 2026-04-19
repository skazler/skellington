"""
SecuritySubagent — vulnerability scanning and security analysis.

Parent: Barrel (Validator)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.utils.json_utils import extract_json


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
        return """You are a security expert. Scan code for vulnerabilities including
injection, XSS, authentication issues, insecure dependencies, data exposure,
and unsafe resource handling.

Respond with ONLY a JSON object — no prose, no fences:
{"passed": bool, "score": float (0-1),
 "vulnerabilities": [{"severity": str, "type": str, "description": str}],
 "recommendations": [str]}"""

    async def run(self, code: str) -> SecurityReport:
        """Perform a security analysis of the given code."""
        response = await self._call_llm(f"Security scan this code:\n\n{code}", temperature=0.1)
        data = extract_json(response)
        data.setdefault("passed", True)
        data.setdefault("score", 1.0)
        data.setdefault("vulnerabilities", [])
        data.setdefault("recommendations", [])
        return SecurityReport(**data)
