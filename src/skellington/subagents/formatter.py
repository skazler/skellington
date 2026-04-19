"""
FormatSubagent — formats content for different output media.

Parent: Mayor (Reporter)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json


class FormattedOutput(BaseModel):
    format: str  # "markdown", "html", "json", "cli"
    content: str
    title: str


class FormatSubagent(BaseSubAgent[FormattedOutput]):
    """Formats content appropriately for the target output medium."""

    name = "formatter"
    parent_agent = AgentName.MAYOR
    emoji = "🎨"
    description = "Formats output for CLI, web, markdown, or other media"

    @property
    def system_prompt(self) -> str:
        return """You are a content formatting expert. Format information clearly for
the target medium (markdown, html, plain text, json).

Respond with ONLY a JSON object — no prose, no fences:
{"format": str, "content": str, "title": str}"""

    async def run(
        self,
        content: str,
        target_format: str = "markdown",
        title: str = "Report",
    ) -> FormattedOutput:
        """Format ``content`` for ``target_format``."""
        response = await self._call_llm(
            f"Format this content as {target_format}:\n\n{content}",
            temperature=0.2,
        )
        data = extract_json(response)
        data.setdefault("format", target_format)
        data.setdefault("content", content)
        data.setdefault("title", title)
        return FormattedOutput(**data)
