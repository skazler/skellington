"""Documentation generation skill for Mayor."""

from __future__ import annotations


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


SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Complete Python source code to generate documentation for (docstrings, README, or API docs)",
        },
        "doc_type": {
            "type": "string",
            "enum": ["docstring", "readme", "api"],
            "description": "Type of documentation to generate (docstring for functions/classes, readme for overview, api for formal reference)",
            "default": "docstring",
        },
    },
    "required": ["code"],
}
