"""
FormatSubagent — formats content for different output media.

Parent: Mayor (Reporter)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


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
the target medium (markdown, HTML, plain text, JSON).
Respond with JSON: {"format": str, "content": str, "title": str}"""

    async def run(self, content: str, target_format: str = "markdown") -> FormattedOutput:
        """Format content for the target medium."""
        response = await self._call_llm(
            f"Format this content as {target_format}:\n\n{content}",
        )
        import json

        data = json.loads(response)
        return FormattedOutput(**data)
