"""
CompareSubagent — side-by-side comparison of options or approaches.

Parent: Oogie (Researcher)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class Comparison(BaseModel):
    items: list[str]
    criteria: list[str]
    matrix: dict[str, dict[str, str]]  # item -> criterion -> assessment
    recommendation: str
    reasoning: str


class CompareSubagent(BaseSubAgent[Comparison]):
    """Compares multiple options across defined criteria."""

    name = "compare"
    parent_agent = AgentName.OOGIE
    emoji = "⚖️"
    description = "Side-by-side comparison of options, tools, or approaches"

    @property
    def system_prompt(self) -> str:
        return """You are an expert analyst who compares options objectively.
Build a comparison matrix and provide a clear recommendation.
Respond with JSON: {"items": [str], "criteria": [str],
"matrix": {"item": {"criterion": "assessment"}}, "recommendation": str, "reasoning": str}"""

    async def run(self, items: list[str], context: str = "") -> Comparison:
        """Compare the given items."""
        items_text = "\n".join(f"- {item}" for item in items)
        response = await self._call_llm(
            f"Compare these options:\n{items_text}\n\nContext: {context}",
            temperature=0.2,
        )
        import json

        data = json.loads(response)
        return Comparison(**data)
