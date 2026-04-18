"""
ContextSubagent — assembles relevant context windows for other agents.

Parent: Zero (Navigator)
Learning goal: context selection. LLM picks which files matter for the task;
we then actually read them from disk. More context is not always better.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.mcp_servers.filesystem import tools as _default_fs
from skellington.utils.json_utils import extract_json

# Guardrails so we don't accidentally ship a megabyte of code into the next LLM call.
_MAX_FILES = 8
_MAX_BYTES_PER_FILE = 20_000
_MAX_CANDIDATES_IN_PROMPT = 300


class RelevantFile(BaseModel):
    path: str
    content: str
    reason: str


class ContextWindow(BaseModel):
    task: str
    relevant_files: list[dict[str, str]]  # kept as dicts for schema compat
    total_tokens_estimate: int
    summary: str


class ContextSubagent(BaseSubAgent[ContextWindow]):
    """Selects the most relevant files for a task and fetches their contents."""

    name = "context"
    parent_agent = AgentName.ZERO
    emoji = "🎯"
    description = "Selects and assembles the most relevant context for a task"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        fs=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._fs = fs or _default_fs

    @property
    def system_prompt(self) -> str:
        return f"""You are Zero's context selector. Given a task description and a
list of candidate file paths, pick the files whose *contents* will most
directly inform the task. Prefer entry points, public APIs, and configuration
over large generated outputs. Pick at most {_MAX_FILES} files.

Respond with ONLY a JSON object — no prose, no fences:
{{"files": [{{"path": "<exact path from the candidate list>", "reason": "<why>"}}]}}"""

    async def run(self, task: str, candidate_paths: list[str]) -> ContextWindow:
        if not candidate_paths:
            return ContextWindow(
                task=task,
                relevant_files=[],
                total_tokens_estimate=0,
                summary="No candidate files provided.",
            )

        selected = await self._select(task, candidate_paths)

        relevant_files: list[dict[str, str]] = []
        total_bytes = 0
        for entry in selected[:_MAX_FILES]:
            path = entry.get("path")
            reason = entry.get("reason", "")
            if not path:
                continue
            try:
                content = await self._fs.read_file(path)
            except Exception as exc:  # noqa: BLE001 — keep going on per-file failures
                self.log.warning("context read_file failed", path=path, error=str(exc))
                continue
            if len(content) > _MAX_BYTES_PER_FILE:
                content = content[:_MAX_BYTES_PER_FILE] + "\n... [truncated]"
            relevant_files.append({"path": path, "content": content, "reason": reason})
            total_bytes += len(content)

        # Rough 4-chars-per-token heuristic.
        token_estimate = total_bytes // 4

        summary = (
            f"Selected {len(relevant_files)} of {len(candidate_paths)} candidate files "
            f"(~{token_estimate} tokens) for task: {task[:80]}"
        )

        return ContextWindow(
            task=task,
            relevant_files=relevant_files,
            total_tokens_estimate=token_estimate,
            summary=summary,
        )

    async def _select(self, task: str, candidates: list[str]) -> list[dict[str, str]]:
        sample = candidates[:_MAX_CANDIDATES_IN_PROMPT]
        trunc = (
            f"\n... ({len(candidates) - len(sample)} more candidates truncated)"
            if len(candidates) > len(sample)
            else ""
        )
        prompt = (
            f"Task:\n{task}\n\n"
            f"Candidate files:\n" + "\n".join(sample) + trunc
        )
        try:
            raw = await self._call_llm(prompt, temperature=0.2)
            data = extract_json(raw)
            files = data.get("files", [])
            return [entry for entry in files if isinstance(entry, dict)]
        except Exception as exc:  # noqa: BLE001
            self.log.warning("context selection failed, using heuristic fallback", error=str(exc))
            # Fallback: take the first few Python/Markdown files as a weak default.
            fallback = [
                {"path": p, "reason": "heuristic fallback"}
                for p in candidates
                if p.endswith((".py", ".md", ".toml"))
            ]
            return fallback[:_MAX_FILES]
