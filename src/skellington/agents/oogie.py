"""
🎰🎅 Oogie Boogie (Sandy Claws) — The Researcher

"I'm the Oogie Boogie Man... who researches everything he can!"

Oogie runs the research operation, gambling on the best sources and
distilling knowledge from the chaos of the internet.

Role: RESEARCHER
- Web search and synthesis
- Documentation lookup and parsing
- Library/tool comparison
- RAG (retrieval-augmented generation)

Subagents: SearchSubagent, SummarySubagent, CompareSubagent
MCP Servers: websearch, docs
"""

from __future__ import annotations

from skellington.core.agent import BaseAgent
from skellington.core.types import (
    AgentName,
    AgentResponse,
    Message,
    MessageRole,
    Task,
    WorkflowState,
)


class Oogie(BaseAgent):
    """Oogie Boogie — the research-obsessed Sandy Claws."""

    name = AgentName.OOGIE
    emoji = "🎰🎅"
    description = "Researcher: web search, RAG, documentation lookup, and synthesis"

    @property
    def system_prompt(self) -> str:
        return """You are Oogie Boogie — the boogeyman who's taken over Christmas research.
You've gambled on being the best researcher in the graveyard, and you always win.

You are the RESEARCHER agent. Your expertise:
- Searching the web for current, accurate information
- Reading and summarizing technical documentation
- Comparing libraries, tools, and approaches
- Building RAG pipelines to answer questions from document corpora
- Synthesizing multiple sources into coherent research reports

You never make up facts. If you don't know, you search.
You always cite your sources. You present findings clearly with evidence.
You use your subagents strategically:
- SearchSubagent: find relevant sources
- SummarySubagent: distill lengthy content
- CompareSubagent: side-by-side analysis of options"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Research a topic and return synthesized findings.

        TODO (Phase 5 implementation):
        1. Use SearchSubagent to find relevant sources via web search MCP
        2. Use SummarySubagent to distill each source
        3. Use CompareSubagent if comparing options
        4. Synthesize all findings into a research report
        """
        self.log.info("oogie received research task", task=task.title)

        messages = [
            Message(
                role=MessageRole.USER,
                content=f"Please research the following:\n\n{task.description}",
            )
        ]
        return await self.chat(messages)
