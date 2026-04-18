"""
DependencySubagent — maps imports, dependencies, and module relationships.

Parent: Zero (Navigator)
Learning goal: deterministic extraction (regex over the real filesystem) first,
LLM interpretation second. The model doesn't guess at imports — it reads them.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.mcp_servers.filesystem import tools as _default_fs

# Python `import foo` / `from foo.bar import baz` — captures the top-level package.
_PY_IMPORT_RE = re.compile(r"^(?:from|import)\s+([a-zA-Z_][\w\.]*)", re.MULTILINE)
_MAX_EDGES_IN_PROMPT = 80


class DependencyEdge(BaseModel):
    from_: str
    to: str
    kind: str = "import"

    # Pydantic v2 allows field aliasing; "from" is reserved so we store as `from_`
    # and serialize / deserialize with an alias.
    model_config = {"populate_by_name": True}


class DependencyGraph(BaseModel):
    modules: list[str]
    edges: list[dict[str, str]]  # [{"from": ..., "to": ..., "kind": ...}]
    external_packages: list[str]
    entry_points: list[str]
    summary: str


class DependencySubagent(BaseSubAgent[DependencyGraph]):
    """Maps import relationships and dependency graphs in a codebase."""

    name = "dependency"
    parent_agent = AgentName.ZERO
    emoji = "🕸️"
    description = "Maps imports, dependencies, and module relationships"

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
        return """You are Zero's dependency analyst. You are given a real,
pre-extracted list of Python import edges from the target codebase. Produce
a short interpretive summary: what the architecture looks like, which
packages are load-bearing, any notable patterns. 2-4 sentences, plain text."""

    async def run(self, path: str) -> DependencyGraph:
        matches = await self._fs.search_files(path, _PY_IMPORT_RE.pattern, file_glob="**/*.py")

        modules: set[str] = set()
        edges: list[dict[str, str]] = []
        external: set[str] = set()
        entry_points: list[str] = []

        root = Path(path).resolve()
        internal_prefixes = _discover_internal_prefixes(root)

        for match_line in matches:
            # `search_files` formats entries as "<absolute_path>:<lineno>: <line>"
            parsed = _parse_match(match_line)
            if parsed is None:
                continue
            filepath, line = parsed
            module = _filepath_to_module(filepath, root)
            if module:
                modules.add(module)

            for import_match in _PY_IMPORT_RE.finditer(line):
                target = import_match.group(1)
                top = target.split(".", 1)[0]
                if top in internal_prefixes:
                    edges.append({"from": module or str(filepath), "to": target, "kind": "import"})
                else:
                    external.add(top)

        # Heuristic entry points: common script names at the root or in top-level folders.
        for filepath in root.rglob("*.py"):
            if filepath.name in {"main.py", "cli.py", "__main__.py", "app.py"}:
                entry_points.append(str(filepath.relative_to(root)))

        summary = await self._summarize(path, modules, edges, external)

        return DependencyGraph(
            modules=sorted(modules),
            edges=edges,
            external_packages=sorted(external),
            entry_points=sorted(set(entry_points)),
            summary=summary,
        )

    async def _summarize(
        self,
        path: str,
        modules: set[str],
        edges: list[dict[str, str]],
        external: set[str],
    ) -> str:
        if not modules and not edges:
            return f"No Python import edges detected under {path}."

        sample_edges = edges[:_MAX_EDGES_IN_PROMPT]
        edge_lines = "\n".join(f"{e['from']} -> {e['to']}" for e in sample_edges)
        trunc = (
            f"\n... ({len(edges) - len(sample_edges)} more edges truncated)"
            if len(edges) > len(sample_edges)
            else ""
        )

        prompt = (
            f"Root: {path}\n"
            f"Internal modules: {len(modules)}\n"
            f"External packages: {', '.join(sorted(external)) or '(none)'}\n\n"
            "Import edges (internal):\n"
            f"{edge_lines}{trunc}"
        )
        try:
            return (await self._call_llm(prompt, temperature=0.2)).strip()
        except Exception as exc:  # noqa: BLE001
            self.log.warning("summary LLM call failed, using fallback", error=str(exc))
            return (
                f"{len(modules)} internal modules, {len(edges)} internal edges, "
                f"{len(external)} external packages."
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_match(match_line: str) -> tuple[Path, str] | None:
    """Parse a 'path:lineno: content' string from search_files into (path, line_content)."""
    # `path` on Windows contains a drive-letter colon, so split with maxsplit=2 from the left
    # but we need to find the ':<digits>:' boundary. Use a regex for safety.
    m = re.match(r"^(.+?):(\d+):\s?(.*)$", match_line)
    if not m:
        return None
    return Path(m.group(1)), m.group(3)


def _filepath_to_module(filepath: Path, root: Path) -> str | None:
    """Convert /abs/path/pkg/sub/mod.py into 'pkg.sub.mod' relative to `root`."""
    try:
        rel = filepath.resolve().relative_to(root)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or None


def _discover_internal_prefixes(root: Path) -> set[str]:
    """
    Collect names that look like internal packages, so we can classify imports as
    internal vs external. We look one and two levels deep — enough for a `src/pkg/`
    layout without walking the whole tree.
    """
    prefixes: set[str] = set()
    for child in root.iterdir() if root.exists() else []:
        if child.is_dir() and not child.name.startswith("."):
            prefixes.add(child.name)
            # src/<pkg> layout
            if child.name in {"src", "lib"}:
                for grandchild in child.iterdir():
                    if grandchild.is_dir() and not grandchild.name.startswith("."):
                        prefixes.add(grandchild.name)
    return prefixes
