"""
🎰🎅 Oogie Boogie (Sandy Claws) — The Researcher

"I'm the Oogie Boogie Man... who researches everything he can!"

Oogie runs the research operation, gambling on the best sources and
distilling knowledge from the chaos of the internet.

Role: RESEARCHER
- Web search (Brave/Tavily, with LLM-imagined fallback)
- Multi-source summarization
- Side-by-side comparison of options
- RAG-style synthesis with citations

Subagents: SearchSubagent, SummarySubagent, CompareSubagent
Toolkits: websearch (via `mcp_servers.websearch.tools`)
"""

from __future__ import annotations

import re

from skellington.core.agent import BaseAgent
from skellington.core.llm import LLMClient
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMProvider,
    Message,
    MessageRole,
    Task,
    WorkflowState,
)
from skellington.mcp_servers.websearch import tools as _default_search
from skellington.subagents.compare import Comparison, CompareSubagent
from skellington.subagents.search import SearchResult, SearchSubagent
from skellington.subagents.summary import Summary, SummarySubagent

from skellington.agents.oogie.skills import (
    ANALYZE_TRENDS_SCHEMA,
    SUMMARIZE_FINDINGS_SCHEMA,
    WEB_SEARCH_SCHEMA,
    analyze_trends,
    summarize_findings,
    web_search,
)

_COMPARE_KEYWORDS = (
    "compare",
    " vs ",
    " vs.",
    " versus ",
    "difference between",
    "which is better",
    "pros and cons",
)

_COMPARE_SPLIT = re.compile(r"\s+vs\.?\s+|\s+versus\s+", re.IGNORECASE)


class Oogie(BaseAgent):
    """Oogie Boogie — the gambling-confident Researcher.

    Web search goes through a `search` toolkit with `web_search(query, num)`.
    By default, Oogie uses the in-process `mcp_servers.websearch.tools` module
    (which calls Brave/Tavily directly when an API key is set, and raises
    SearchAPIError when none is). When the toolkit is missing or raises,
    SearchSubagent falls back to LLM-imagined results so the pipeline still
    runs end-to-end in dev/learning mode.
    """

    name = AgentName.OOGIE
    emoji = "🎰🎅"
    description = "Researcher: web search, RAG, documentation lookup, and synthesis"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        search=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._search = search or _default_search

        # Register skills
        self.register_tool(name="web_search", func=web_search, schema=WEB_SEARCH_SCHEMA)
        self.register_tool(name="analyze_trends", func=analyze_trends, schema=ANALYZE_TRENDS_SCHEMA)
        self.register_tool(
            name="summarize_findings",
            func=summarize_findings,
            schema=SUMMARIZE_FINDINGS_SCHEMA,
        )

    @property
    def system_prompt(self) -> str:
        return """You are Oogie Boogie — the boogeyman who's taken over Christmas research.
You've gambled on being the best researcher in the graveyard, and you always win.

You are the RESEARCHER agent. Your expertise:
- Searching the web for current, accurate information
- Reading and summarizing technical documentation
- Comparing libraries, tools, and approaches
- Synthesizing multiple sources into coherent research reports

You have access to these skills:
- web_search: Search the web for information on any topic
- analyze_trends: Find patterns and trends in data or code
- summarize_findings: Create concise summaries of research content

You never make up facts. If you don't know, you search.
You always cite your sources. You present findings clearly with evidence."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Research a topic and return synthesized findings.

        Flow:
        1. SearchSubagent finds candidate sources (real toolkit or LLM fallback)
        2. SummarySubagent distills the top hits in sequence
        3. CompareSubagent runs when the user is comparing options
        4. Synthesize a research report and publish to state.metadata['research']
        """
        intent = _classify_intent(task)
        query = (task.description or task.title).strip()
        num_results = int((task.context or {}).get("num_results", 5))
        max_summaries = int((task.context or {}).get("max_summaries", 3))
        self.log.info("oogie researching", task=task.title, intent=intent, query=query)

        search_result: SearchResult = await SearchSubagent(
            llm_client=self._llm, search=self._search
        ).run(query, num_results=num_results)

        summaries = await self._summarize_top_hits(search_result, max_summaries)
        comparison = await self._maybe_compare(intent, task, query)

        state.metadata.setdefault("research", {})[str(task.id)] = {
            "query": query,
            "intent": intent,
            "result_count": search_result.total_found,
            "sources": search_result.results,
            "summaries": [s.model_dump() for s in summaries],
            "comparison": comparison.model_dump() if comparison else None,
        }

        return await self._synthesize(task, query, intent, search_result, summaries, comparison)

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _summarize_top_hits(
        self, search_result: SearchResult, max_summaries: int
    ) -> list[Summary]:
        if not search_result.results or max_summaries <= 0:
            return []
        summarizer = SummarySubagent(llm_client=self._llm)
        summaries: list[Summary] = []
        for hit in search_result.results[:max_summaries]:
            content = _hit_to_text(hit)
            try:
                summaries.append(await summarizer.run(content))
            except Exception as exc:  # noqa: BLE001
                self.log.warning("summary failed for hit", url=hit.get("url"), error=str(exc))
        return summaries

    async def _maybe_compare(self, intent: str, task: Task, query: str) -> Comparison | None:
        if intent != "compare":
            return None
        items = _extract_compare_items(task)
        if len(items) < 2:
            self.log.info("compare intent without enough items, skipping", items=items)
            return None
        try:
            return await CompareSubagent(llm_client=self._llm).run(items, context=query)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("compare failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        task: Task,
        query: str,
        intent: str,
        search_result: SearchResult,
        summaries: list[Summary],
        comparison: Comparison | None,
    ) -> AgentResponse:
        sources_block = (
            "\n".join(f"- {r.get('title', '?')}: {r.get('url', '')}" for r in search_result.results)
            or "(no sources found)"
        )
        summaries_block = (
            "\n".join(f"- {s.title}: {s.full_summary[:200]}" for s in summaries) or "(no summaries)"
        )
        compare_block = (
            f"Comparison verdict: {comparison.recommendation}\nReasoning: {comparison.reasoning}"
            if comparison
            else ""
        )

        prompt = (
            f"You just finished researching: {query}\n"
            f"Intent: {intent}\n\n"
            f"Sources:\n{sources_block}\n\n"
            f"Summaries:\n{summaries_block}\n\n"
            f"{compare_block}\n\n"
            "Write a concise research report (~5-8 sentences) in Oogie's "
            "gambler-confident tone. Cite at least one source by title."
        )
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.chat(messages)
        response.task_id = task.id
        response.metadata = {
            **response.metadata,
            "intent": intent,
            "query": query,
            "source_count": len(search_result.results),
            "summary_count": len(summaries),
            "compared": comparison is not None,
        }
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_intent(task: Task) -> str:
    """Route to 'compare' or 'research' by keyword heuristic."""
    text = f" {task.title}\n{task.description or ''} ".lower()
    if any(k in text for k in _COMPARE_KEYWORDS):
        return "compare"
    return "research"


def _extract_compare_items(task: Task) -> list[str]:
    """Pull comparison items from `task.context['items']`, else split the description."""
    ctx = task.context or {}
    raw = ctx.get("items")
    if isinstance(raw, list) and raw:
        return [str(i).strip() for i in raw if str(i).strip()]
    text = task.description or task.title
    parts = _COMPARE_SPLIT.split(text)
    return [p.strip(" .?,") for p in parts if p.strip() and len(p.strip()) < 80]


def _hit_to_text(hit: dict[str, str]) -> str:
    title = hit.get("title", "")
    snippet = hit.get("snippet", "")
    url = hit.get("url", "")
    return f"{title}\n{url}\n\n{snippet}".strip()
