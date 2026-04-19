"""
DiffSubagent — generates readable diffs showing before/after changes.

Parent: Mayor (Reporter)

Note: actual unified-diff text is computed deterministically with ``difflib``
(LLMs hallucinate diffs). The LLM only writes the human-readable
``change_summary`` and ``files_changed`` list.
"""

from __future__ import annotations

import difflib

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName
from skellington.utils.json_utils import extract_json


class DiffReport(BaseModel):
    files_changed: list[str]
    additions: int
    deletions: int
    diff_text: str
    change_summary: str


class DiffSubagent(BaseSubAgent[DiffReport]):
    """Generates readable diffs between before and after states."""

    name = "diff"
    parent_agent = AgentName.MAYOR
    emoji = "📊"
    description = "Generates readable diffs and changelogs"

    @property
    def system_prompt(self) -> str:
        return """You are a diff narrator. Given a unified diff, write a brief, human
summary of what changed and why it matters.

Respond with ONLY a JSON object — no prose, no fences:
{"change_summary": str}"""

    async def run(self, before: str, after: str, filename: str = "file") -> DiffReport:
        """Compute the diff for ``filename`` and let the LLM narrate it."""
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
            )
        )
        diff_text = "".join(diff_lines)
        additions = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        files_changed = [filename] if diff_text else []

        if not diff_text:
            return DiffReport(
                files_changed=[],
                additions=0,
                deletions=0,
                diff_text="",
                change_summary="No changes.",
            )

        response = await self._call_llm(
            f"Summarize this diff in one or two sentences:\n\n{diff_text}",
            temperature=0.2,
        )
        data = extract_json(response)
        return DiffReport(
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            diff_text=diff_text,
            change_summary=str(data.get("change_summary", "Changes applied.")),
        )
