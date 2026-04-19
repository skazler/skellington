"""
SearchSubagent — performs web searches via an injected toolkit, with an
LLM-imagined fallback for development/learning use.

Parent: Oogie (Researcher)
Learning goal: how a subagent talks to a real external API (Brave/Tavily)
through a swappable toolkit, the same way Sally/Zero talk to filesystem.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.utils.json_utils import extract_json


class SearchResult(BaseModel):
    query: str
    results: list[dict[str, str]]  # [{"title", "url", "snippet"}]
    total_found: int


class SearchSubagent(BaseSubAgent[SearchResult]):
    """Searches the web. Uses a real toolkit when available, falls back to LLM."""

    name = "search"
    parent_agent = AgentName.OOGIE
    emoji = "🔍"
    description = "Performs web searches and returns structured results"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        search=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        # Toolkit exposes `await search.web_search(query, num) -> list[dict]`.
        # When None or it raises, we fall back to LLM-imagined results.
        self._search = search

    @property
    def system_prompt(self) -> str:
        return """You are a web search specialist. Given a query, return the top
search results that a real engine would surface.

Respond with ONLY a JSON object — no prose, no fences:
{"query": str, "results": [{"title": str, "url": str, "snippet": str}], "total_found": int}"""

    async def run(self, query: str, num_results: int = 5) -> SearchResult:
        """Search the web for ``query``."""
        if self._search is not None:
            try:
                hits = await self._search.web_search(query, num_results)
                return SearchResult(
                    query=query,
                    results=list(hits),
                    total_found=len(hits),
                )
            except Exception as exc:  # noqa: BLE001 — toolkit failure → LLM fallback
                self.log.warning("toolkit search failed; falling back to LLM", error=str(exc))

        response = await self._call_llm(
            f"Generate the top {num_results} plausible search results for: '{query}'.\n"
            "Return JSON only.",
            temperature=0.3,
        )
        data = extract_json(response)
        data.setdefault("query", query)
        data.setdefault("results", [])
        data.setdefault("total_found", len(data.get("results", [])))
        return SearchResult(**data)
