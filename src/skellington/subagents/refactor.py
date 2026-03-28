"""
RefactorSubagent — improves existing code quality.

Parent: Sally (Builder)
Learning goal: Code transformation with preservation of behavior.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class RefactoredCode(BaseModel):
    code: str
    changes_made: list[str]
    behavior_preserved: bool


class RefactorSubagent(BaseSubAgent[RefactoredCode]):
    """Refactors existing code for clarity, performance, or style."""

    name = "refactor"
    parent_agent = AgentName.SALLY
    emoji = "🔧"
    description = "Improves existing code quality without changing behavior"

    @property
    def system_prompt(self) -> str:
        return """You are an expert at code refactoring. Improve code quality while preserving behavior.

Focus on: readability, type hints, reduced complexity, better naming, PEP 8.
Respond with JSON: {"code": str, "changes_made": [str], "behavior_preserved": bool}"""

    async def run(self, code: str, goals: list[str] | None = None) -> RefactoredCode:
        """Refactor code toward specified goals."""
        goal_text = "\n".join(goals) if goals else "general quality improvement"
        response = await self._call_llm(
            f"Refactor this code (goals: {goal_text}):\n\n{code}",
        )
        import json

        data = json.loads(response)
        return RefactoredCode(**data)
