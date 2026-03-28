"""
SummarySubagent — distills lengthy content into concise summaries.

Parent: Oogie (Researcher)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class Summary(BaseModel):
    title: str
    key_points: list[str]
    full_summary: str
    word_count_original: int
    word_count_summary: int


class SummarySubagent(BaseSubAgent[Summary]):
    """Distills long content into structured summaries."""

    name = "summary"
    parent_agent = AgentName.OOGIE
    emoji = "📝"
    description = "Distills lengthy content into concise, structured summaries"

    @property
    def system_prompt(self) -> str:
        return """You are an expert summarizer. Extract the most important information
from any text and present it clearly.
Respond with JSON: {"title": str, "key_points": [str], "full_summary": str,
"word_count_original": int, "word_count_summary": int}"""

    async def run(self, content: str, max_points: int = 5) -> Summary:
        """Summarize the given content."""
        response = await self._call_llm(
            f"Summarize this content (max {max_points} key points):\n\n{content}",
            temperature=0.3,
        )
        import json

        data = json.loads(response)
        return Summary(**data)
