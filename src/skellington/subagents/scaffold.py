"""
ScaffoldSubagent — generates project directory structures and templates.

Parent: Sally (Builder)
Learning goal: multi-file structured output. The subagent describes what the
project should look like; the parent writes it to disk.
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.llm import LLMClient
from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName, LLMProvider
from skellington.mcp_servers.filesystem import tools as _default_fs
from skellington.utils.json_utils import extract_json


class ScaffoldPlan(BaseModel):
    project_name: str
    files: dict[str, str]  # relative path -> content
    setup_commands: list[str]


class ScaffoldSubagent(BaseSubAgent[ScaffoldPlan]):
    """Generates complete project scaffolding."""

    name = "scaffold"
    parent_agent = AgentName.SALLY
    emoji = "🏗️"
    description = "Creates project scaffolding and boilerplate"

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
        return """You generate complete project scaffolding. Given a project description,
output all necessary files and their contents.

File paths must be relative (e.g. "src/app.py", "tests/test_app.py", "README.md").
Do not include a leading slash or drive letter.

Respond with ONLY a JSON object — no prose, no fences:
{"project_name": str, "files": {"<relative path>": "<content>"}, "setup_commands": [str]}"""

    async def run(self, description: str, project_name: str = "my_project") -> ScaffoldPlan:
        """Generate project scaffold from description."""
        response = await self._call_llm(
            f"Scaffold a project named '{project_name}':\n\n{description}",
            temperature=0.3,
        )
        data = extract_json(response)
        data.setdefault("project_name", project_name)
        data.setdefault("files", {})
        data.setdefault("setup_commands", [])
        return ScaffoldPlan(**data)
