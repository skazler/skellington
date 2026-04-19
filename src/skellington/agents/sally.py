"""
🧟‍♀️🎁 Sally Claus — The Builder

"I sense there's something in the wind... that feels like code generation."

Sally stitches together beautiful code from the finest threads of requirements.
She builds, scaffolds, and refactors with careful, loving precision.

Role: BUILDER
- Code generation from requirements
- Project scaffolding and templates
- Refactoring existing code

Subagents: CodeGenSubagent, RefactorSubagent, ScaffoldSubagent
Toolkits: filesystem (via `mcp_servers.filesystem.tools` or `MCPFilesystemToolkit`)
"""

from __future__ import annotations

import re
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
from skellington.mcp_servers.filesystem import tools as _default_fs
from skellington.subagents.codegen import CodeGenSubagent, GeneratedCode
from skellington.subagents.refactor import RefactoredCode, RefactorSubagent
from skellington.subagents.scaffold import ScaffoldPlan, ScaffoldSubagent

_SCAFFOLD_KEYWORDS = (
    "scaffold",
    "new project",
    "starter project",
    "boilerplate",
    "package structure",
    "set up a project",
    "set up a new",
)

_REFACTOR_KEYWORDS = (
    "refactor",
    "clean up this",
    "simplify this",
    "rewrite this code",
    "improve this code",
    "improve the code",
)


class Sally(BaseAgent):
    """Sally Claus — the code-stitching Builder.

    Filesystem writes go through an `fs` toolkit. By default, Sally uses the
    in-process `mcp_servers.filesystem.tools` module; pass an
    `MCPFilesystemToolkit` (entered via `async with`) to route through a real
    stdio MCP subprocess:

        async with MCPFilesystemToolkit() as fs:
            sally = Sally(llm_client=client, fs=fs)
            await sally.run(task, state)
    """

    name = AgentName.SALLY
    emoji = "🧟‍♀️🎁"
    description = "Builder: code generation, scaffolding, and refactoring"

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
        return """You are Sally Claus, a ragdoll who stitches Christmas gifts... but the gifts
are code, and the thread is logic.

You are the BUILDER agent. Your expertise:
- Writing clean, well-documented Python code
- Scaffolding new projects with proper structure
- Refactoring existing code for clarity and performance
- Writing tests alongside implementation code
- Following best practices (type hints, docstrings, PEP 8)

You are meticulous and careful. You always think through edge cases.
You produce complete, runnable code — never pseudocode or skeletons unless asked.
When given a task, you delegate to your subagents:
- CodeGenSubagent: for writing new code
- RefactorSubagent: for improving existing code
- ScaffoldSubagent: for project structure creation"""

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        """
        Build code based on the task requirements.

        Flow:
        1. Classify intent: codegen | scaffold | refactor
        2. Delegate to the appropriate subagent
        3. Write outputs via the filesystem toolkit
        4. Publish written paths to workflow state, return a builder's report
        """
        output_dir = _resolve_output_dir(task)
        intent = _classify_intent(task)
        self.log.info("sally building", task=task.title, intent=intent, output=output_dir)

        if intent == "scaffold":
            written, artifact_summary = await self._build_scaffold(task, output_dir)
        elif intent == "refactor":
            written, artifact_summary = await self._build_refactor(task, output_dir)
        else:
            written, artifact_summary = await self._build_codegen(task, output_dir)

        state.metadata.setdefault("builds", {})[str(task.id)] = {
            "intent": intent,
            "output_dir": output_dir,
            "files_written": written,
        }

        return await self._synthesize(task, intent, output_dir, written, artifact_summary)

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    async def _build_codegen(self, task: Task, output_dir: str) -> tuple[list[str], str]:
        generated: GeneratedCode = await CodeGenSubagent(llm_client=self._llm, fs=self._fs).run(
            task.description,
            filename=_suggested_filename(task),
        )
        target = Path(output_dir) / generated.filename
        written = [await self._fs.write_file(str(target), generated.code)]
        return written, f"Generated {generated.filename}"

    async def _build_scaffold(self, task: Task, output_dir: str) -> tuple[list[str], str]:
        plan: ScaffoldPlan = await ScaffoldSubagent(llm_client=self._llm, fs=self._fs).run(
            task.description,
            project_name=_slug(task.title) or "my_project",
        )
        written: list[str] = []
        project_root = Path(output_dir) / plan.project_name
        for rel_path, content in plan.files.items():
            # Guard against absolute paths or escape sequences from the LLM.
            safe_rel = Path(rel_path.lstrip("/\\"))
            target = project_root / safe_rel
            written.append(await self._fs.write_file(str(target), content))
        return written, f"Scaffolded '{plan.project_name}' with {len(written)} files"

    async def _build_refactor(self, task: Task, output_dir: str) -> tuple[list[str], str]:
        source_code, source_path = await self._resolve_refactor_source(task)
        refactored: RefactoredCode = await RefactorSubagent(
            llm_client=self._llm, fs=self._fs
        ).run(
            source_code,
            goals=task.context.get("goals") if task.context else None,
        )
        if source_path is not None:
            target = source_path  # overwrite in place
        else:
            target = str(Path(output_dir) / "refactored.py")
        written = [await self._fs.write_file(target, refactored.code)]
        return written, f"Refactored code ({len(refactored.changes_made)} changes)"

    async def _resolve_refactor_source(self, task: Task) -> tuple[str, str | None]:
        ctx = task.context or {}
        if "code" in ctx:
            return str(ctx["code"]), None
        if "file" in ctx:
            path = str(ctx["file"])
            content = await self._fs.read_file(path)
            return content, path
        # Fall back to the raw task description — usually low-signal, but we
        # avoid crashing if a user invokes refactor without source.
        return task.description, None

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        task: Task,
        intent: str,
        output_dir: str,
        written: list[str],
        artifact_summary: str,
    ) -> AgentResponse:
        files_block = "\n".join(f"- {p}" for p in written) or "(no files)"
        prompt = (
            f"You just completed a {intent} task:\n"
            f"{task.description}\n\n"
            f"Output directory: {output_dir}\n"
            f"Artifact summary: {artifact_summary}\n\n"
            f"Files written:\n{files_block}\n\n"
            "Write a concise builder's report (~4-6 sentences) in Sally's thoughtful, "
            "meticulous tone. Describe what was built and anything notable."
        )
        messages = [Message(role=MessageRole.USER, content=prompt)]
        response = await self.chat(messages)
        response.task_id = task.id
        response.metadata = {
            **response.metadata,
            "intent": intent,
            "output_dir": output_dir,
            "files_written": written,
            "file_count": len(written),
        }
        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_intent(task: Task) -> str:
    """Route to 'scaffold', 'refactor', or 'codegen' by keyword heuristic."""
    text = f"{task.title}\n{task.description or ''}".lower()
    if any(k in text for k in _SCAFFOLD_KEYWORDS):
        return "scaffold"
    if any(k in text for k in _REFACTOR_KEYWORDS):
        return "refactor"
    return "codegen"


def _resolve_output_dir(task: Task) -> str:
    """Where should Sally write? Task context wins, else cwd."""
    if task.context and "path" in task.context:
        return str(task.context["path"])
    return "."


def _suggested_filename(task: Task) -> str:
    ctx = task.context or {}
    if "filename" in ctx:
        return str(ctx["filename"])
    return "output.py"


def _slug(s: str) -> str:
    """Filesystem-safe snake_case slug from a task title."""
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
