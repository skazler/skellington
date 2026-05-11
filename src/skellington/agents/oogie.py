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

# ------------------------------------------------------------------
# Skill Functions
# ------------------------------------------------------------------


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for information on a given query.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        Formatted search results
    """
    try:
        # Use the search subagent
        search_agent = SearchSubagent()
        results = await search_agent.run(query)

        # Format results
        formatted_results = []
        for i, result in enumerate(results.results[:max_results], 1):
            formatted_results.append(f"""
{i}. **{result.title}**
   URL: {result.url}
   Summary: {result.snippet}
   Relevance: {result.relevance_score:.2f}
""")

        report = f"🔍 Web Search Results for: '{query}'\\n"
        report += f"Found {len(results.results)} results, showing top {min(max_results, len(results.results))}\\n\\n"
        report += "".join(formatted_results)

        return report

    except Exception as e:
        return f"Error performing web search: {str(e)}"


async def analyze_trends(data: str, data_type: str = "text") -> str:
    """
    Analyze trends and patterns in data or code.

    Args:
        data: The data to analyze (text, code, or structured data)
        data_type: Type of data ("text", "code", "json", "csv")

    Returns:
        Trend analysis report
    """
    try:
        analysis = []

        if data_type == "code":
            # Analyze code patterns
            import re

            # Count common patterns
            functions = len(re.findall(r"def \w+", data))
            classes = len(re.findall(r"class \w+", data))
            imports = len(re.findall(r"^(import|from)", data, re.MULTILINE))
            comments = len(re.findall(r"#.*", data))

            analysis.append(f"📊 Code Analysis:")
            analysis.append(f"- Functions: {functions}")
            analysis.append(f"- Classes: {classes}")
            analysis.append(f"- Imports: {imports}")
            analysis.append(f"- Comments: {comments}")

            # Calculate ratios
            total_lines = len(data.split("\\n"))
            code_density = (total_lines - comments) / total_lines if total_lines > 0 else 0
            analysis.append(f"- Code density: {code_density:.2f} (lines of code vs comments)")

            # Identify patterns
            if functions > classes * 2:
                analysis.append("⚡ Pattern: Function-heavy codebase (procedural style)")
            elif classes > functions:
                analysis.append("🏗️ Pattern: Class-heavy codebase (OOP style)")

            if imports > 10:
                analysis.append("📦 Pattern: Heavy external dependencies")

        elif data_type == "text":
            # Analyze text patterns
            words = data.split()
            sentences = re.split(r"[.!?]+", data)

            analysis.append(f"📝 Text Analysis:")
            analysis.append(f"- Total words: {len(words)}")
            analysis.append(f"- Total sentences: {len(sentences)}")
            analysis.append(f"- Average words per sentence: {len(words)/len(sentences):.1f}")

            # Find common words
            word_freq = {}
            for word in words:
                word = word.lower().strip(".,!?")
                if len(word) > 3:  # Skip short words
                    word_freq[word] = word_freq.get(word, 0) + 1

            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            analysis.append(
                f"- Most common words: {', '.join([f'{word}({count})' for word, count in top_words])}"
            )

        elif data_type == "json":
            # Analyze JSON structure
            import json

            parsed = json.loads(data)

            def analyze_json(obj, path=""):
                results = []
                if isinstance(obj, dict):
                    results.append(f"📂 Object at {path}: {len(obj)} keys")
                    for key, value in obj.items():
                        results.extend(analyze_json(value, f"{path}.{key}" if path else key))
                elif isinstance(obj, list):
                    results.append(f"📋 Array at {path}: {len(obj)} items")
                    if obj and len(obj) <= 3:  # Sample small arrays
                        for i, item in enumerate(obj):
                            results.extend(analyze_json(item, f"{path}[{i}]"))
                else:
                    results.append(f"📄 Value at {path}: {type(obj).__name__}")
                return results

            analysis.extend(analyze_json(parsed))

        else:
            analysis.append(f"❓ Unsupported data type: {data_type}")

        return "\\n".join(analysis)

    except Exception as e:
        return f"Error analyzing trends: {str(e)}"


async def summarize_findings(content: str, max_length: int = 300) -> str:
    """
    Create a concise summary of research findings or content.

    Args:
        content: The content to summarize
        max_length: Maximum length of summary in words

    Returns:
        Concise summary
    """
    try:
        # Simple extractive summarization
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Score sentences by position and length
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            # Prefer sentences in the middle and at the end (conclusion)
            position_score = 1.0
            if i < len(sentences) * 0.2:  # First 20%
                position_score = 0.7
            elif i > len(sentences) * 0.8:  # Last 20%
                position_score = 1.2

            # Prefer longer sentences (likely more informative)
            length_score = min(len(sentence.split()) / 10, 2.0)

            # Prefer sentences with key terms
            key_terms = [
                "important",
                "significant",
                "key",
                "main",
                "conclusion",
                "result",
                "finding",
            ]
            keyword_score = 1.0 + sum(1 for term in key_terms if term in sentence.lower()) * 0.5

            total_score = position_score * length_score * keyword_score
            scored_sentences.append((sentence, total_score))

        # Select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        selected_sentences = scored_sentences[:5]  # Top 5 sentences

        # Sort back to original order for coherence
        selected_sentences.sort(key=lambda x: sentences.index(x[0]))

        summary = " ".join([s[0] for s in selected_sentences])

        # Truncate if too long
        words = summary.split()
        if len(words) > max_length:
            summary = " ".join(words[:max_length]) + "..."

        return f"📋 Summary ({len(words)} words):\\n\\n{summary}"

    except Exception as e:
        return f"Error summarizing findings: {str(e)}"


# ------------------------------------------------------------------
# Skill Schemas
# ------------------------------------------------------------------

WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "The search query to look up on the web"},
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return",
            "default": 5,
            "minimum": 1,
            "maximum": 20,
        },
    },
    "required": ["query"],
}

ANALYZE_TRENDS_SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "string", "description": "The data to analyze for trends and patterns"},
        "data_type": {
            "type": "string",
            "enum": ["text", "code", "json", "csv"],
            "description": "Type of data being analyzed",
            "default": "text",
        },
    },
    "required": ["data"],
}

SUMMARIZE_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "The content to summarize"},
        "max_length": {
            "type": "integer",
            "description": "Maximum length of summary in words",
            "default": 300,
            "minimum": 50,
            "maximum": 1000,
        },
    },
    "required": ["content"],
}

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
            name="summarize_findings", func=summarize_findings, schema=SUMMARIZE_FINDINGS_SCHEMA
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
