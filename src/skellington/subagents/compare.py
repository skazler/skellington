"""
CompareSubagent — side-by-side comparison of options or approaches.

Parent: Oogie (Researcher)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json


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

Respond with ONLY a JSON object — no prose, no fences:
{"items": [str], "criteria": [str],
 "matrix": {"item": {"criterion": "assessment"}},
 "recommendation": str, "reasoning": str}"""

    async def run(self, items: list[str], context: str = "") -> Comparison:
        """Compare ``items`` against each other, optionally given ``context``."""
        items_text = "\n".join(f"- {item}" for item in items)
        response = await self._call_llm(
            f"Compare these options:\n{items_text}\n\nContext: {context}",
            temperature=0.2,
        )
        data = extract_json(response)
        data.setdefault("items", list(items))
        data.setdefault("criteria", [])
        data.setdefault("matrix", {})
        data.setdefault("recommendation", "")
        data.setdefault("reasoning", "")
        return Comparison(**data)
