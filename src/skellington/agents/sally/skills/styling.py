"""Code style analysis skill for Sally."""

from __future__ import annotations


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


SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Complete Python source code string to lint for PEP 8 compliance, unused imports, and missing docstrings",
        }
    },
    "required": ["code"],
}
