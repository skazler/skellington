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

# ------------------------------------------------------------------
# Skill Functions
# ------------------------------------------------------------------


async def generate_documentation(code: str, doc_type: str = "docstring") -> str:
    """
    Generate documentation for Python code.

    Args:
        code: Python code to document
        doc_type: Type of documentation ("docstring", "readme", "api")

    Returns:
        Generated documentation
    """
    try:
        import ast
        import re

        tree = ast.parse(code)

        if doc_type == "docstring":
            # Generate docstrings for functions and classes
            docs = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    name = node.name
                    docstring = ast.get_docstring(node)

                    if not docstring:
                        # Generate basic docstring
                        params = []
                        returns = "None"

                        if isinstance(node, ast.FunctionDef):
                            # Extract parameters
                            for arg in node.args.args:
                                param_name = arg.arg
                                param_type = "Any"
                                if arg.annotation:
                                    param_type = ast.unparse(arg.annotation)
                                params.append(f"{param_name}: {param_type}")

                            # Try to infer return type
                            if node.returns:
                                returns = ast.unparse(node.returns)

                        param_str = ", ".join(params) if params else ""

                        docstring = f'''\"\"\"{name.title().replace('_', ' ')}.

Args:
    {param_str}

Returns:
    {returns}
\"\"\"'''

                        docs.append(f"Add to {name}:\n{docstring}")

            if docs:
                return "📚 Suggested Docstrings:\n\n" + "\n\n".join(docs)
            else:
                return "✅ All functions and classes already have docstrings!"

        elif doc_type == "readme":
            # Generate a basic README
            functions = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)

            readme = f"""# Code Documentation

## Classes
{chr(10).join(f"- `{cls}`" for cls in classes)}

## Functions  
{chr(10).join(f"- `{func}`" for func in functions)}

## Usage
```python
# Import and use the code here
```
"""
            return readme

        elif doc_type == "api":
            # Generate API documentation
            api_docs = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    name = node.name
                    params = []

                    for arg in node.args.args:
                        param_name = arg.arg
                        param_type = "Any"
                        if arg.annotation:
                            param_type = ast.unparse(arg.annotation)
                        params.append(f"{param_name}: {param_type}")

                    returns = "None"
                    if node.returns:
                        returns = ast.unparse(node.returns)

                    api_docs.append(f"""### `{name}({', '.join(params)})`

**Returns:** `{returns}`

{ast.get_docstring(node) or "No description available."}
""")

            return f"# API Documentation\n\n{chr(10).join(api_docs)}"

        else:
            return f"❓ Unsupported documentation type: {doc_type}"

    except Exception as e:
        return f"Error generating documentation: {str(e)}"


async def create_visualizations(data: str, chart_type: str = "bar") -> str:
    """
    Create visualizations from data.

    Args:
        data: Data to visualize (JSON, CSV, or structured text)
        chart_type: Type of chart ("bar", "line", "pie", "histogram")

    Returns:
        ASCII art visualization or description
    """
    try:
        import json

        # Try to parse as JSON first
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # Try to parse as simple key-value pairs
            parsed_data = {}
            for line in data.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    try:
                        parsed_data[key.strip()] = float(value.strip())
                    except ValueError:
                        parsed_data[key.strip()] = value.strip()

        if not isinstance(parsed_data, dict):
            return "❌ Data must be a dictionary/object with numeric values for visualization"

        # Filter to numeric values only
        numeric_data = {k: v for k, v in parsed_data.items() if isinstance(v, (int, float))}

        if not numeric_data:
            return "❌ No numeric data found for visualization"

        if chart_type == "bar":
            # Create ASCII bar chart
            max_value = max(numeric_data.values())
            max_label_len = max(len(str(k)) for k in numeric_data.keys())

            chart = "📊 Bar Chart\n\n"
            for key, value in numeric_data.items():
                bar_length = int((value / max_value) * 20) if max_value > 0 else 0
                bar = "█" * bar_length
                chart += f"{str(key):<{max_label_len}} | {bar} {value}\n"

            return chart

        elif chart_type == "pie":
            # Simple text-based pie chart representation
            total = sum(numeric_data.values())
            chart = "🥧 Pie Chart Breakdown\n\n"

            for key, value in numeric_data.items():
                percentage = (value / total * 100) if total > 0 else 0
                bars = int(percentage / 5)  # 20 bars = 100%
                bar_chart = "█" * bars
                chart += f"{key}: {bar_chart} {percentage:.1f}%\n"

            return chart

        elif chart_type == "line":
            # Simple line chart
            values = list(numeric_data.values())
            labels = list(numeric_data.keys())

            chart = "📈 Line Chart\n\n"
            max_val = max(values) if values else 0
            min_val = min(values) if values else 0
            range_val = max_val - min_val if max_val != min_val else 1

            for i, (label, value) in enumerate(zip(labels, values)):
                # Normalize to 0-10 scale
                normalized = int(((value - min_val) / range_val) * 10) if range_val > 0 else 0
                line = " " * normalized + "●"
                chart += f"{label}: {line} {value}\n"

            return chart

        else:
            return f"❓ Unsupported chart type: {chart_type}. Try 'bar', 'pie', or 'line'."

    except Exception as e:
        return f"Error creating visualization: {str(e)}"


async def format_reports(data: str, output_format: str = "markdown") -> str:
    """
    Convert data to different output formats.

    Args:
        data: Data to format
        output_format: Target format ("markdown", "json", "csv", "html")

    Returns:
        Formatted data
    """
    try:
        import json
        import csv
        import io

        # Try to parse input data
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            # Assume it's text data, try to structure it
            parsed_data = {"content": data}

        if output_format == "json":
            return json.dumps(parsed_data, indent=2)

        elif output_format == "markdown":
            if isinstance(parsed_data, dict):
                md = "# Formatted Report\n\n"
                for key, value in parsed_data.items():
                    if isinstance(value, (list, dict)):
                        md += f"## {key.title()}\n\n"
                        if isinstance(value, list):
                            for item in value:
                                md += f"- {item}\n"
                        else:
                            for k, v in value.items():
                                md += f"- **{k}**: {v}\n"
                    else:
                        md += f"## {key.title()}\n\n{value}\n\n"
                return md
            else:
                return f"# Report\n\n{parsed_data}"

        elif output_format == "csv":
            if isinstance(parsed_data, list) and parsed_data and isinstance(parsed_data[0], dict):
                # List of dictionaries
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=parsed_data[0].keys())
                writer.writeheader()
                writer.writerows(parsed_data)
                return output.getvalue()
            elif isinstance(parsed_data, dict):
                # Single dictionary
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Key", "Value"])
                for key, value in parsed_data.items():
                    writer.writerow([key, str(value)])
                return output.getvalue()
            else:
                return f"Key,Value\\nContent,{parsed_data}"

        elif output_format == "html":
            html = "<!DOCTYPE html><html><head><title>Report</title></head><body>"
            html += "<h1>Formatted Report</h1>"

            if isinstance(parsed_data, dict):
                for key, value in parsed_data.items():
                    html += f"<h2>{key.title()}</h2>"
                    if isinstance(value, list):
                        html += "<ul>"
                        for item in value:
                            html += f"<li>{item}</li>"
                        html += "</ul>"
                    else:
                        html += f"<p>{value}</p>"
            else:
                html += f"<p>{parsed_data}</p>"

            html += "</body></html>"
            return html

        else:
            return (
                f"❓ Unsupported format: {output_format}. Try 'markdown', 'json', 'csv', or 'html'."
            )

    except Exception as e:
        return f"Error formatting report: {str(e)}"


# ------------------------------------------------------------------
# Skill Schemas
# ------------------------------------------------------------------

GENERATE_DOCUMENTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Python code to generate documentation for"},
        "doc_type": {
            "type": "string",
            "enum": ["docstring", "readme", "api"],
            "description": "Type of documentation to generate",
            "default": "docstring",
        },
    },
    "required": ["code"],
}

CREATE_VISUALIZATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "string", "description": "Data to visualize (JSON or key-value pairs)"},
        "chart_type": {
            "type": "string",
            "enum": ["bar", "line", "pie", "histogram"],
            "description": "Type of chart to create",
            "default": "bar",
        },
    },
    "required": ["data"],
}

FORMAT_REPORTS_SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "string", "description": "Data to format"},
        "output_format": {
            "type": "string",
            "enum": ["markdown", "json", "csv", "html"],
            "description": "Output format for the data",
            "default": "markdown",
        },
    },
    "required": ["data"],
}


class Mayor(BaseAgent):
    """The Mayor — two-faced reporter of Halloween/Christmas Town."""

    name = AgentName.MAYOR
    emoji = "🎭📊"
    description = "Reporter: result synthesis, formatting, status reporting"

    def __init__(self, llm_client=None, provider=None):
        super().__init__(llm_client=llm_client, provider=provider)

        # Register skills
        self.register_tool(
            name="generate_documentation",
            func=generate_documentation,
            schema=GENERATE_DOCUMENTATION_SCHEMA,
        )
        self.register_tool(
            name="create_visualizations",
            func=create_visualizations,
            schema=CREATE_VISUALIZATIONS_SCHEMA,
        )
        self.register_tool(name="format_reports", func=format_reports, schema=FORMAT_REPORTS_SCHEMA)

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

You have access to these skills:
- generate_documentation: Create docstrings, READMEs, and API docs
- create_visualizations: Generate charts and graphs from data
- format_reports: Convert data to different formats (JSON, CSV, HTML, Markdown)

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
