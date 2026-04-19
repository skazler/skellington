"""
CodeGenSubagent — writes new code from specifications.

Parent: Sally (Builder)
Learning goal: structured code generation. The subagent produces code as
structured output; the parent (Sally) is responsible for persisting it.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.mcp_servers.filesystem import tools as _default_fs
from skellington.utils.json_utils import extract_json


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

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        fs=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._fs = fs or _default_fs

    @property
    def system_prompt(self) -> str:
        return """You are an expert Python developer writing production-quality code.

Always include:
- Full type hints
- Google-style docstrings
- Error handling
- No placeholder or TODO code

Respond with ONLY a JSON object — no prose, no fences:
{"filename": str, "language": str, "code": str, "explanation": str}"""

    async def run(self, specification: str, filename: str = "output.py") -> GeneratedCode:
        """Generate code from a specification."""
        response = await self._call_llm(
            f"Generate code for: {specification}\nTarget filename: {filename}",
            temperature=0.2,
        )
        data = extract_json(response)
        # Respect the caller's preferred filename if the LLM drifted.
        data.setdefault("filename", filename)
        return GeneratedCode(**data)
