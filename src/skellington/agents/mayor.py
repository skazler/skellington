"""
🎭📊 The Mayor of Halloween/Christmas Town — The Reporter

"I'm the Mayor of Halloween Town! I can't make decisions by myself!"

The Mayor always has two faces — one happy (good news), one sad (bad news).
He formats results, generates reports, and communicates findings to users.

Role: REPORTER
- Collect findings the specialist agents publish to ``state.metadata``
- Generate a workflow status snapshot
- Optionally diff before/after content (passed via task.context)
- Format the final answer for the requested medium

Subagents: FormatSubagent, DiffSubagent, StatusSubagent
"""

from __future__ import annotations

from typing import Any

from skellington.core.agent import BaseAgent
from skellington.core.types import (
    AgentName,
    AgentResponse,
    Message,
    MessageRole,
    Task,
    WorkflowState,
)
from skellington.subagents.diff import DiffReport, DiffSubagent
from skellington.subagents.formatter import FormattedOutput, FormatSubagent
from skellington.subagents.status import StatusReport, StatusSubagent


class Mayor(BaseAgent):
    """The Mayor — two-faced reporter of Halloween/Christmas Town."""

    name = AgentName.MAYOR
    emoji = "🎭📊"
    description = "Reporter: result synthesis, formatting, status reporting"

    @property
    def system_prompt(self) -> str:
        return """You are the Mayor of Halloween/Christmas Town — with your megaphone and your
two faces (one for good news 😊, one for bad news 😟).

You are the REPORTER agent. Your expertise:
- Synthesizing results from multiple agents into clear, readable reports
- Formatting output appropriately for the context (markdown, CLI, JSON)
- Generating progress updates and status summaries
- Creating diffs and changelogs showing what changed
- Presenting both good news and bad news with equal clarity

You are the voice that users hear. Be clear, organized, and informative."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Collect findings from state.metadata and produce a final report.

        Flow:
        1. StatusSubagent — counts tasks + LLM-narrated progress summary
        2. DiffSubagent — only when ``task.context`` includes ``before`` and ``after``
        3. Build a "findings" digest from state.metadata (research/builds/navigation/validation)
        4. FormatSubagent — render the digest in the requested format (default: markdown)
        """
        ctx = task.context or {}
        target_format = str(ctx.get("format", "markdown"))
        self.log.info("mayor reporting", task=task.title, format=target_format)

        status: StatusReport = await StatusSubagent(llm_client=self._llm).run(state)

        diff: DiffReport | None = None
        if "before" in ctx and "after" in ctx:
            diff = await DiffSubagent(llm_client=self._llm).run(
                str(ctx["before"]),
                str(ctx["after"]),
                filename=str(ctx.get("filename", "file")),
            )

        digest = _build_digest(state, status, diff)
        formatted: FormattedOutput = await FormatSubagent(llm_client=self._llm).run(
            digest,
            target_format=target_format,
            title=ctx.get("title", "Skellington Report"),
        )

        state.metadata.setdefault("reports", {})[str(task.id)] = {
            "format": formatted.format,
            "title": formatted.title,
            "status": status.model_dump(),
            "diff": diff.model_dump() if diff else None,
        }

        return await self._synthesize(task, formatted, status, diff)

    async def _synthesize(
        self,
        task: Task,
        formatted: FormattedOutput,
        status: StatusReport,
        diff: DiffReport | None,
    ) -> AgentResponse:
        diff_block = (
            f"Diff: {diff.additions} additions, {diff.deletions} deletions"
            f" — {diff.change_summary}"
            if diff
            else ""
        )
        prompt = (
            f"You just finished reporting for the user.\n"
            f"Status: {status.completed}/{status.total_tasks} tasks complete "
            f"({status.percentage_complete}%). {status.narrative}\n"
            f"{diff_block}\n\n"
            f"Final formatted report:\n{formatted.content}\n\n"
            "Speak in the Mayor's two-faced megaphone voice (~3-5 sentences). "
            "Lead with good news if any tasks completed, sad news if any failed."
        )
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.chat(messages)
        response.task_id = task.id
        response.metadata = {
            **response.metadata,
            "format": formatted.format,
            "title": formatted.title,
            "report": formatted.content,
            "completed": status.completed,
            "failed": status.failed,
            "total_tasks": status.total_tasks,
            "percentage_complete": status.percentage_complete,
            "diffed": diff is not None,
        }
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_digest(
    state: WorkflowState,
    status: StatusReport,
    diff: DiffReport | None,
) -> str:
    """Compose a plain-text digest from state.metadata for the formatter."""
    lines: list[str] = []
    lines.append(f"User request: {state.user_request}")
    lines.append("")
    lines.append(
        f"Progress: {status.completed}/{status.total_tasks} complete "
        f"({status.percentage_complete}%), {status.failed} failed."
    )
    if status.narrative:
        lines.append(status.narrative)
    if status.next_steps:
        lines.append("")
        lines.append("Next steps:")
        for step in status.next_steps:
            lines.append(f"  - {step}")

    meta = state.metadata or {}
    nav_section = _navigation_section(meta.get("navigation"))
    if nav_section:
        lines.extend(["", "Navigation findings:", *nav_section])

    builds_section = _builds_section(meta.get("builds"))
    if builds_section:
        lines.extend(["", "Build artifacts:", *builds_section])

    research_section = _research_section(meta.get("research"))
    if research_section:
        lines.extend(["", "Research findings:", *research_section])

    validation_section = _validation_section(meta.get("validation"))
    if validation_section:
        lines.extend(["", "Validation verdicts:", *validation_section])

    if diff:
        lines.extend(
            [
                "",
                f"Diff ({diff.additions}+, {diff.deletions}-):",
                f"  {diff.change_summary}",
            ]
        )

    return "\n".join(lines)


def _navigation_section(nav: dict[str, Any] | None) -> list[str]:
    if not nav:
        return []
    out: list[str] = []
    for path, info in nav.items():
        out.append(f"  - {path}: {len(info.get('relevant_files', []))} relevant files")
    return out


def _builds_section(builds: dict[str, Any] | None) -> list[str]:
    if not builds:
        return []
    out: list[str] = []
    for _, info in builds.items():
        files = info.get("files_written", [])
        out.append(f"  - {info.get('intent', '?')}: {len(files)} files written")
        for f in files[:5]:
            out.append(f"      • {f}")
    return out


def _research_section(research: dict[str, Any] | None) -> list[str]:
    if not research:
        return []
    out: list[str] = []
    for _, info in research.items():
        out.append(
            f"  - query={info.get('query', '?')!r}: "
            f"{info.get('result_count', 0)} sources, "
            f"{len(info.get('summaries', []))} summarized"
        )
        comparison = info.get("comparison")
        if comparison:
            out.append(f"      verdict: {comparison.get('recommendation', '')}")
    return out


def _validation_section(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return []
    out: list[str] = []
    for _, consensus in validation.items():
        passed = consensus.get("passed")
        out.append(
            f"  - consensus: {'PASS' if passed else 'FAIL'} "
            f"(avg score {consensus.get('average_score', 0):.2f}) — "
            f"{consensus.get('summary', '')}"
        )
    return out
