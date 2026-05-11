"""Import optimization skill for Sally."""

from __future__ import annotations


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


SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Python source code to optimize by removing unused imports and organizing them into stdlib, third-party, and local groups",
        }
    },
    "required": ["code"],
}
