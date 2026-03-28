"""
CodeGenSubagent — writes new code from specifications.

Parent: Sally (Builder)
Learning goal: Structured code generation with quality constraints.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class GeneratedCode(BaseModel):
    """Output from a code generation request."""

    filename: str
    language: str
    code: str
    explanation: str


class CodeGenSubagent(BaseSubAgent[GeneratedCode]):
    """Generates new code from a specification."""

    name = "codegen"
    parent_agent = AgentName.SALLY
    emoji = "✍️"
    description = "Writes new code from requirements"

    @property
    def system_prompt(self) -> str:
        return """You are an expert Python developer writing production-quality code.

Always include:
- Full type hints
- Google-style docstrings
- Error handling
- No placeholder or TODO code

Respond with JSON:
{"filename": str, "language": str, "code": str, "explanation": str}"""

    async def run(self, specification: str, filename: str = "output.py") -> GeneratedCode:
        """Generate code from a specification."""
        response = await self._call_llm(
            f"Generate code for: {specification}\nTarget filename: {filename}",
            temperature=0.2,
        )
        import json

        data = json.loads(response)
        return GeneratedCode(**data)
