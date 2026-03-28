"""
DependencySubagent — maps imports, dependencies, and module relationships.

Parent: Zero (Navigator)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class DependencyGraph(BaseModel):
    modules: list[str]
    edges: list[dict[str, str]]  # [{"from": ..., "to": ..., "type": ...}]
    external_packages: list[str]
    entry_points: list[str]
    summary: str


class DependencySubagent(BaseSubAgent[DependencyGraph]):
    """Maps import relationships and dependency graphs in a codebase."""

    name = "dependency"
    parent_agent = AgentName.ZERO
    emoji = "🕸️"
    description = "Maps imports, dependencies, and module relationships"

    @property
    def system_prompt(self) -> str:
        return """You are a dependency analyst. Given code or a file structure,
map out all import relationships and dependencies.
Respond with JSON: {"modules": [str], "edges": [{"from": str, "to": str, "type": str}],
"external_packages": [str], "entry_points": [str], "summary": str}"""

    async def run(self, code_or_path: str) -> DependencyGraph:
        """Analyze dependencies in the given code or path."""
        response = await self._call_llm(
            f"Analyze the dependencies:\n\n{code_or_path}",
        )
        import json

        data = json.loads(response)
        return DependencyGraph(**data)
