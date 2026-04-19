"""
SummarySubagent — distills lengthy content into concise summaries.

Parent: Oogie (Researcher)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json


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
        return """You are an expert summarizer. Extract the most important
information from any text and present it clearly.

Respond with ONLY a JSON object — no prose, no fences:
{"title": str, "key_points": [str], "full_summary": str,
 "word_count_original": int, "word_count_summary": int}"""

    async def run(self, content: str, max_points: int = 5) -> Summary:
        """Summarize ``content`` into ``max_points`` key points."""
        response = await self._call_llm(
            f"Summarize this content (max {max_points} key points):\n\n{content}",
            temperature=0.3,
        )
        data = extract_json(response)
        original_words = len(content.split())
        data.setdefault("title", "Summary")
        data.setdefault("key_points", [])
        data.setdefault("full_summary", "")
        data.setdefault("word_count_original", original_words)
        data.setdefault(
            "word_count_summary",
            len(str(data.get("full_summary", "")).split()),
        )
        return Summary(**data)
