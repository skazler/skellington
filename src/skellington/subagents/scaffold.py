"""
ScaffoldSubagent — generates project directory structures and templates.

Parent: Sally (Builder)
"""

from __future__ import annotations

from pydantic import BaseModel

from skellington.core.subagent import BaseSubAgent
from skellington.core.types import AgentName


class ScaffoldPlan(BaseModel):
    project_name: str
    files: dict[str, str]  # path -> content
    setup_commands: list[str]


class ScaffoldSubagent(BaseSubAgent[ScaffoldPlan]):
    """Generates complete project scaffolding."""

    name = "scaffold"
    parent_agent = AgentName.SALLY
    emoji = "🏗️"
    description = "Creates project scaffolding and boilerplate"

    @property
    def system_prompt(self) -> str:
        return """You generate complete project scaffolding. Given a project description,
output all necessary files and their contents as a JSON structure.
Respond with JSON: {"project_name": str, "files": {"path": "content"}, "setup_commands": [str]}"""

    async def run(self, description: str, project_name: str = "my_project") -> ScaffoldPlan:
        """Generate project scaffold from description."""
        response = await self._call_llm(
            f"Scaffold a project named '{project_name}':\n\n{description}",
            temperature=0.3,
        )
        import json

        data = json.loads(response)
        return ScaffoldPlan(**data)
