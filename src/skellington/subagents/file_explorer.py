"""
FileExplorerSubagent — traverses and catalogs file system structures.

Parent: Zero (Navigator)
Learning goal: deterministic traversal (via the filesystem toolkit) combined
with a single LLM call for qualitative summary. The structure is *facts* —
we don't ask the model to hallucinate a directory listing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.llm import LLMClient
from skellington.core.types import AgentName, LLMProvider
from skellington.mcp_servers.filesystem import tools as _default_fs

# Keep the LLM prompt to a reasonable size on large repos.
_MAX_ENTRIES_IN_PROMPT = 300
# Common noise we always skip when mapping a tree.
_IGNORED_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
}


class FileTree(BaseModel):
    root_path: str
    tree: dict[str, list[str]]  # directory (relative) -> [file names]
    total_files: int
    file_types: dict[str, int]  # extension -> count
    summary: str


class FileExplorerSubagent(BaseSubAgent[FileTree]):
    """Traverses and catalogs file system structures."""

    name = "file_explorer"
    parent_agent = AgentName.ZERO
    emoji = "📂"
    description = "Traverses and maps file system structures"

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
        return """You are Zero's file-system explorer. You are given a pre-computed
directory listing (the ground truth — the files really exist). Your only job
is to produce a short, high-signal summary of what this codebase or directory
appears to be, based solely on the listing.

Keep the summary to 2-4 sentences. No speculation about contents you can't
see from filenames. Respond with plain text — no JSON, no markdown fences."""

    async def run(self, path: str, max_depth: int = 4) -> FileTree:
        entries = await self._fs.list_directory(path, recursive=True)
        root = Path(path)

        tree: dict[str, list[str]] = defaultdict(list)
        extension_counts: Counter[str] = Counter()
        total_files = 0

        for rel in entries:
            parts = PurePosixPath(rel.replace("\\", "/")).parts
            if any(part in _IGNORED_PARTS for part in parts):
                continue
            if len(parts) > max_depth:
                continue
            # `list_directory` includes directories too — filter them out so the tree
            # only buckets real files.
            if not (root / rel).is_file():
                continue

            directory = "/".join(parts[:-1]) or "."
            filename = parts[-1]
            tree[directory].append(filename)
            total_files += 1
            if "." in filename:
                extension_counts[filename.rsplit(".", 1)[-1].lower()] += 1

        summary = await self._summarize(path, dict(tree), extension_counts, total_files)

        return FileTree(
            root_path=path,
            tree=dict(tree),
            total_files=total_files,
            file_types=dict(extension_counts),
            summary=summary,
        )

    async def _summarize(
        self,
        path: str,
        tree: dict[str, list[str]],
        extensions: Counter[str],
        total_files: int,
    ) -> str:
        if total_files == 0:
            return f"{path} appears to be empty or contains no indexable files."

        # Flatten a sample of entries for the prompt.
        sample_lines: list[str] = []
        for directory, files in sorted(tree.items()):
            for fname in files:
                prefix = "" if directory == "." else f"{directory}/"
                sample_lines.append(f"{prefix}{fname}")
                if len(sample_lines) >= _MAX_ENTRIES_IN_PROMPT:
                    break
            if len(sample_lines) >= _MAX_ENTRIES_IN_PROMPT:
                break

        truncation_note = (
            f"\n... ({total_files - len(sample_lines)} more entries truncated)"
            if total_files > len(sample_lines)
            else ""
        )
        ext_line = ", ".join(f"{ext}={n}" for ext, n in extensions.most_common(10))

        prompt = (
            f"Root: {path}\n"
            f"Total files: {total_files}\n"
            f"File types: {ext_line}\n\n"
            "Listing:\n"
            + "\n".join(sample_lines)
            + truncation_note
        )

        try:
            return (await self._call_llm(prompt, temperature=0.2)).strip()
        except Exception as exc:  # noqa: BLE001 — summary is best-effort
            self.log.warning("summary LLM call failed, using fallback", error=str(exc))
            return f"{path}: {total_files} files across {len(tree)} directories ({ext_line})."
