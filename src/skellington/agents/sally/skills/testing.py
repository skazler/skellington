"""Unit test generation skill for Sally."""

from __future__ import annotations


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
        import ast

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
                f"        {p.split(':')[0]} = {_get_test_value(p.split(':')[1].strip())}"
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
                    f"        {p.split(':')[0]} = {_get_edge_value(p.split(':')[1].strip())}"
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


def _get_test_value(param_type: str) -> str:
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


def _get_edge_value(param_type: str) -> str:
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


SCHEMA = {
    "type": "object",
    "properties": {
        "function_code": {
            "type": "string",
            "description": "Complete Python function code (including def statement) to generate comprehensive unit tests for",
        },
        "function_name": {
            "type": "string",
            "description": "Python function name to test (must match function definition in code)",
            "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
        },
    },
    "required": ["function_code", "function_name"],
}
