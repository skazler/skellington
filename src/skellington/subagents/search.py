"""
SearchSubagent — performs web searches via MCP web search server.

Parent: Oogie (Researcher)
Learning goal: MCP tool integration in a subagent.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class SearchResult(BaseModel):
    query: str
    results: list[dict[str, str]]  # [{"title": ..., "url": ..., "snippet": ...}]
    total_found: int


class SearchSubagent(BaseSubAgent[SearchResult]):
    """Searches the web using the websearch MCP server."""

    name = "search"
    parent_agent = AgentName.OOGIE
    emoji = "🔍"
    description = "Performs web searches and returns structured results"

    @property
    def system_prompt(self) -> str:
        return """You are a web search specialist. Given a query, formulate the best
search terms and return structured results.
TODO: Connect to websearch MCP server for real results.
Respond with JSON: {"query": str, "results": [{"title": str, "url": str, "snippet": str}], "total_found": int}"""

    async def run(self, query: str, num_results: int = 5) -> SearchResult:
        """Search the web for the given query."""
        # TODO: Replace with actual MCP websearch tool call
        response = await self._call_llm(
            f"What would be the top {num_results} search results for: '{query}'?\n"
            "Provide realistic-looking results in JSON format.",
        )
        import json

        data = json.loads(response)
        return SearchResult(**data)
