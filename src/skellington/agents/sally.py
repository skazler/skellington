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

# ------------------------------------------------------------------
# Skill Functions
# ------------------------------------------------------------------


async def generate_unit_tests(function_code: str, function_name: str) -> str:
    """
    Generate comprehensive unit tests for a Python function.

    Args:
        function_code: The complete function code to test
        function_name: Name of the function being tested

    Returns:
        Generated test code as a string
    """
    try:
        # Parse function signature to understand parameters
        import ast
        import inspect

        # Extract function parameters and types
        tree = ast.parse(function_code)
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                func_def = node
                break

        if not func_def:
            return f"Error: Could not find function '{function_name}' in provided code"

        # Extract parameters
        params = []
        for arg in func_def.args.args:
            param_name = arg.arg
            param_type = "Any"
            if arg.annotation:
                param_type = ast.unparse(arg.annotation)
            params.append(f"{param_name}: {param_type}")

        # Generate test cases based on parameter types
        test_cases = []

        # Basic functionality test
        arrange_section = "\\n".join(
            [
                f"        {p.split(':')[0]} = {get_test_value(p.split(':')[1].strip())}"
                for p in params
            ]
        )
        act_params = ", ".join([p.split(":")[0] for p in params])

        test_cases.append(f"""
    def test_{function_name}_basic(self):
        \"\"\"Test basic functionality of {function_name}.\"\"\"
        # Arrange
{arrange_section}
        
        # Act
        result = {function_name}({act_params})
        
        # Assert
        self.assertIsNotNone(result)  # Basic smoke test
""")

        # Edge cases
        if any("str" in p for p in params):
            edge_arrange_section = "\\n".join(
                [
                    f"        {p.split(':')[0]} = {get_edge_value(p.split(':')[1].strip())}"
                    for p in params
                ]
            )

            test_cases.append(f"""
    def test_{function_name}_empty_string(self):
        \"\"\"Test {function_name} with empty string inputs.\"\"\"
        # Arrange
{edge_arrange_section}
        
        # Act & Assert
        with self.assertRaises(ValueError):
            {function_name}({act_params})
""")

        # Generate the complete test class
        error_arrange = "\\n".join([f"        {p.split(':')[0]} = None" for p in params])
        error_test = f"""
    def test_{function_name}_error_handling(self):
        \"\"\"Test error handling in {function_name}.\"\"\"
        # Arrange
{error_arrange}
        
        # Act & Assert
        with self.assertRaises((TypeError, ValueError)):
            {function_name}({act_params})
"""

        test_code = f"""import unittest
from {function_name.split('_')[0]}_module import {function_name}

class Test{function_name.title().replace('_', '')}(unittest.TestCase):
    \"\"\"Unit tests for {function_name} function.\"\"\"
    
{"".join(test_cases)}{error_test}
if __name__ == '__main__':
    unittest.main()
"""

        return test_code

    except Exception as e:
        return f"Error generating tests: {str(e)}"


def get_test_value(param_type: str) -> str:
    """Get a test value based on parameter type."""
    if "str" in param_type.lower():
        return '"test_value"'
    elif "int" in param_type.lower():
        return "42"
    elif "float" in param_type.lower():
        return "3.14"
    elif "bool" in param_type.lower():
        return "True"
    elif "list" in param_type.lower():
        return "[1, 2, 3]"
    elif "dict" in param_type.lower():
        return '{"key": "value"}'
    else:
        return "None"


def get_edge_value(param_type: str) -> str:
    """Get an edge case value based on parameter type."""
    if "str" in param_type.lower():
        return '""'
    elif "int" in param_type.lower():
        return "-1"
    elif "float" in param_type.lower():
        return "0.0"
    elif "bool" in param_type.lower():
        return "False"
    elif "list" in param_type.lower():
        return "[]"
    elif "dict" in param_type.lower():
        return "{}"
    else:
        return "None"


async def check_code_style(code: str) -> str:
    """
    Analyze Python code for style issues and suggest improvements.

    Args:
        code: Python code to analyze

    Returns:
        Style analysis report with suggestions
    """
    try:
        import ast
        import re

        issues = []

        # Parse the code
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"Syntax Error: {e}"

        # Check line length (PEP 8: max 79 characters)
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > 79:
                issues.append(f"Line {i}: Too long ({len(line)} chars, max 79)")

        # Check for proper imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        # Check for unused imports (simplified check)
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)

        unused_imports = []
        for imp in imports:
            base_name = imp.split(".")[-1]
            if base_name not in used_names and not imp.startswith("__"):
                unused_imports.append(imp)

        if unused_imports:
            issues.append(f"Unused imports: {', '.join(unused_imports)}")

        # Check for docstrings
        functions_without_docs = []
        classes_without_docs = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not ast.get_docstring(node):
                    functions_without_docs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if not ast.get_docstring(node):
                    classes_without_docs.append(node.name)

        if functions_without_docs:
            issues.append(f"Functions without docstrings: {', '.join(functions_without_docs)}")
        if classes_without_docs:
            issues.append(f"Classes without docstrings: {', '.join(classes_without_docs)}")

        # Check for type hints
        functions_without_hints = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_hints = bool(node.returns or any(arg.annotation for arg in node.args.args))
                if not has_hints:
                    functions_without_hints.append(node.name)

        if functions_without_hints:
            issues.append(f"Functions without type hints: {', '.join(functions_without_hints)}")

        # Generate report
        if not issues:
            return "✅ Code style check passed! No issues found."

        report = "🔍 Code Style Analysis:\\n\\n"
        report += f"Issues found: {len(issues)}\\n\\n"

        for issue in issues:
            report += f"• {issue}\\n"

        report += "\\n💡 Suggestions:\\n"
        if any("docstring" in issue for issue in issues):
            report += "• Add docstrings to all public functions and classes\\n"
        if any("type hint" in issue for issue in issues):
            report += "• Add type hints to function parameters and return types\\n"
        if any("Unused imports" in issue for issue in issues):
            report += "• Remove unused imports\\n"
        if any("Too long" in issue for issue in issues):
            report += "• Break long lines into multiple lines (max 79 chars)\\n"

        return report

    except Exception as e:
        return f"Error analyzing code style: {str(e)}"


async def optimize_imports(code: str) -> str:
    """
    Analyze and optimize Python import statements.

    Args:
        code: Python code to optimize imports for

    Returns:
        Optimized code with cleaned up imports
    """
    try:
        import ast
        import re

        # Parse the code
        tree = ast.parse(code)

        # Extract all import statements
        imports = []
        import_froms = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.append(node)
            elif isinstance(node, ast.ImportFrom):
                import_froms.append(node)

        # Find used names
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)

        # Filter imports to only keep used ones
        optimized_imports = []
        optimized_import_froms = []

        # Process regular imports
        for imp in imports:
            used_aliases = []
            for alias in imp.names:
                if alias.asname:
                    if alias.asname in used_names:
                        used_aliases.append(alias)
                else:
                    base_name = alias.name.split(".")[0]
                    if base_name in used_names:
                        used_aliases.append(alias)

            if used_aliases:
                new_imp = ast.Import(names=used_aliases)
                optimized_imports.append(new_imp)

        # Process from imports
        for imp_from in import_froms:
            used_aliases = []
            for alias in imp_from.names:
                name_to_check = alias.asname if alias.asname else alias.name
                if name_to_check in used_names:
                    used_aliases.append(alias)

            if used_aliases:
                new_imp_from = ast.ImportFrom(
                    module=imp_from.module, names=used_aliases, level=imp_from.level
                )
                optimized_import_froms.append(new_imp_from)

        # Group imports by type
        stdlib_imports = []
        third_party_imports = []
        local_imports = []

        # Simple heuristic for import categorization
        for imp in optimized_imports + optimized_import_froms:
            if isinstance(imp, ast.Import):
                module_name = imp.names[0].name.split(".")[0]
            else:
                module_name = imp.module.split(".")[0] if imp.module else ""

            if module_name in {
                "os",
                "sys",
                "re",
                "json",
                "datetime",
                "collections",
                "itertools",
                "functools",
            }:
                stdlib_imports.append(imp)
            elif "." in module_name or module_name.startswith("_"):
                local_imports.append(imp)
            else:
                third_party_imports.append(imp)

        # Generate optimized code
        lines = code.split("\n")
        import_lines = []

        # Add imports in order: stdlib, third-party, local
        for imp_group in [stdlib_imports, third_party_imports, local_imports]:
            if imp_group:
                for imp in imp_group:
                    import_lines.append(ast.unparse(imp))
                import_lines.append("")  # Empty line between groups

        # Find where original imports end
        code_lines = []
        in_imports = True
        past_imports = False

        for line in lines:
            stripped = line.strip()
            if past_imports:
                code_lines.append(line)
            elif in_imports and (stripped.startswith("import ") or stripped.startswith("from ")):
                continue  # Skip original import lines
            elif in_imports and stripped and not stripped.startswith("#"):
                # Found first non-import, non-comment line
                if import_lines:
                    code_lines.extend(import_lines[:-1])  # Remove last empty line
                    code_lines.append("")
                code_lines.append(line)
                past_imports = True
                in_imports = False
            else:
                code_lines.append(line)

        if not past_imports and import_lines:
            # No code after imports, add imports at end
            code_lines.extend(import_lines)

        optimized_code = "\n".join(code_lines)

        # Report what was changed
        original_import_count = len(imports) + len(import_froms)
        optimized_import_count = len(optimized_imports) + len(optimized_import_froms)

        report = f"Import optimization complete:\\n"
        report += f"- Original imports: {original_import_count}\\n"
        report += f"- Optimized imports: {optimized_import_count}\\n"
        report += f"- Removed {original_import_count - optimized_import_count} unused imports\\n\\n"
        report += "Optimized code:\\n```python\\n" + optimized_code + "\\n```"

        return report

    except Exception as e:
        return f"Error optimizing imports: {str(e)}"


# ------------------------------------------------------------------
# Skill Schemas
# ------------------------------------------------------------------

GENERATE_UNIT_TESTS_SCHEMA = {
    "type": "object",
    "properties": {
        "function_code": {
            "type": "string",
            "description": "The complete Python function code to generate tests for",
        },
        "function_name": {"type": "string", "description": "Name of the function to test"},
    },
    "required": ["function_code", "function_name"],
}

CHECK_CODE_STYLE_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Python code to analyze for style issues"}
    },
    "required": ["code"],
}

OPTIMIZE_IMPORTS_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Python code to optimize imports for"}
    },
    "required": ["code"],
}

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

        # Register skills
        self.register_tool(
            name="generate_unit_tests", func=generate_unit_tests, schema=GENERATE_UNIT_TESTS_SCHEMA
        )
        self.register_tool(
            name="check_code_style", func=check_code_style, schema=CHECK_CODE_STYLE_SCHEMA
        )
        self.register_tool(
            name="optimize_imports", func=optimize_imports, schema=OPTIMIZE_IMPORTS_SCHEMA
        )

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

You have access to these skills:
- generate_unit_tests: Generate comprehensive unit tests for Python functions
- check_code_style: Analyze code for style issues and suggest improvements
- optimize_imports: Clean up and organize import statements

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
        refactored: RefactoredCode = await RefactorSubagent(llm_client=self._llm, fs=self._fs).run(
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
