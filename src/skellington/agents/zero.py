"""
👻🔴 Zero — The Navigator

Zero leads the way through dark codebases with a glowing Rudolph nose.

Role: NAVIGATOR
- File system exploration and analysis
- Codebase understanding and mapping
- Dependency graph construction
- Building context windows for other agents

Subagents: FileExplorerSubagent, DependencySubagent, ContextSubagent
Toolkits: filesystem (via `mcp_servers.filesystem.tools`)
"""

from __future__ import annotations

from pathlib import Path

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
from skellington.subagents.context import ContextSubagent, ContextWindow
from skellington.subagents.dependency import DependencyGraph, DependencySubagent
from skellington.subagents.file_explorer import FileExplorerSubagent, FileTree


class Zero(BaseAgent):
    """Zero — the ghostly codebase navigator.

    Filesystem access goes through an `fs` toolkit with read_file / write_file /
    list_directory / search_files methods. By default, Zero uses the in-process
    `mcp_servers.filesystem.tools` module. For orthodox MCP, the caller can
    pass an `MCPFilesystemToolkit` (entered via `async with`) instead:

        async with MCPFilesystemToolkit() as fs:
            zero = Zero(llm_client=client, fs=fs)
            await zero.run(task, state)
    """

    name = AgentName.ZERO
    emoji = "👻🔴"
    description = "Navigator: file exploration, codebase analysis, dependency mapping"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        provider: LLMProvider | None = None,
        fs=None,
    ) -> None:
        super().__init__(llm_client=llm_client, provider=provider)
        self._fs = fs  # None → subagents fall back to the direct tools module

    @property
    def system_prompt(self) -> str:
        return """You are Zero, the ghost dog with a glowing red nose who leads the way
through dark, unfamiliar codebases.

You are the NAVIGATOR agent. Your expertise:
- Exploring and mapping file system structures
- Understanding codebases: reading files, tracing dependencies, finding patterns
- Building rich context windows so other agents can work effectively
- Identifying the most relevant files for a given task

You are precise and systematic. You explore methodically, not randomly.
You always build a mental map before diving into details."""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Navigate and analyze a codebase.

        Flow:
        1. FileExplorerSubagent maps the directory tree
        2. DependencySubagent extracts the import graph
        3. ContextSubagent picks the most task-relevant files
        4. Synthesize a navigator's report via a final LLM call
        """
        target_path = _resolve_target_path(task)
        self.log.info("zero navigating", task=task.title, path=target_path)

        tree = await FileExplorerSubagent(llm_client=self._llm, fs=self._fs).run(target_path)
        deps = await DependencySubagent(llm_client=self._llm, fs=self._fs).run(target_path)

        candidates = _flatten_tree_to_paths(tree)
        context = await ContextSubagent(llm_client=self._llm, fs=self._fs).run(
            task.description, candidates
        )

        # Publish findings so downstream specialists (Sally, Oogie, Mayor) can pick them up
        # without re-walking the filesystem.
        state.metadata.setdefault("navigation", {})[target_path] = {
            "tree_summary": tree.summary,
            "dependency_summary": deps.summary,
            "relevant_files": [f["path"] for f in context.relevant_files],
        }

        return await self._synthesize(task, target_path, tree, deps, context)

    async def _synthesize(
        self,
        task: Task,
        target_path: str,
        tree: FileTree,
        deps: DependencyGraph,
        context: ContextWindow,
    ) -> AgentResponse:
        selected_block = "\n".join(
            f"- {f['path']}: {f.get('reason', '')}" for f in context.relevant_files
        ) or "(none selected)"

        prompt = (
            f"You just finished navigating `{target_path}` for this task:\n"
            f"{task.description}\n\n"
            f"Structure summary:\n{tree.summary}\n\n"
            f"Dependency summary:\n{deps.summary}\n\n"
            f"Most relevant files for the task:\n{selected_block}\n\n"
            "Write a concise navigator's report (~5-8 sentences) that synthesizes "
            "what was found. Speak with Zero's quiet, methodical tone."
        )
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.chat(messages)
        response.task_id = task.id
        response.metadata = {
            **response.metadata,
            "target_path": target_path,
            "total_files": tree.total_files,
            "internal_modules": len(deps.modules),
            "external_packages": len(deps.external_packages),
            "context_files_selected": len(context.relevant_files),
        }
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_target_path(task: Task) -> str:
    """Pick the directory Zero should navigate. Task context wins, else default to cwd."""
    if task.context and "path" in task.context:
        return str(task.context["path"])
    return "."


def _flatten_tree_to_paths(tree: FileTree) -> list[str]:
    """Convert FileTree's {dir: [files]} back into absolute paths for read_file()."""
    root = Path(tree.root_path).resolve()
    paths: list[str] = []
    for directory, files in tree.tree.items():
        base = root if directory == "." else root / directory
        for fname in files:
            paths.append(str(base / fname))
    return paths
