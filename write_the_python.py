"""Utilities for dynamically writing Python function source code to files.

This module exposes :func:`write_python_function`, a helper that composes a
syntactically valid Python function definition from its constituent parts
(name, parameters, return annotation, docstring and body) and persists it to
disk. The generated file is validated with :func:`ast.parse` before being
written so callers can be confident the resulting module is importable.

Example:
    >>> write_python_function(
    ...     filename="greet.py",
    ...     name="greet",
    ...     parameters=[("name", "str", None)],
    ...     return_type="str",
    ...     docstring="Return a friendly greeting.",
    ...     body="return f'Hello, {name}!'",
    ... )
"""

from __future__ import annotations

import ast
import keyword
import os
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

# A parameter is a triple of (name, optional_type_annotation, optional_default).
Parameter = Tuple[str, Optional[str], Optional[str]]
PathLike = Union[str, os.PathLike]


def _validate_identifier(name: str, kind: str) -> None:
    """Ensure ``name`` is a valid, non-reserved Python identifier.

    Args:
        name: The identifier to validate.
        kind: A human readable label used in error messages (e.g. ``"function"``).

    Raises:
        ValueError: If ``name`` is not a valid Python identifier or is a
            reserved keyword.
    """
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError(f"Invalid {kind} name: {name!r}")
    if keyword.iskeyword(name):
        raise ValueError(f"{kind.capitalize()} name {name!r} is a reserved keyword")


def _format_parameters(parameters: Sequence[Parameter]) -> str:
    """Render a parameter list into its textual form.

    Args:
        parameters: An iterable of ``(name, annotation, default)`` triples. The
            ``annotation`` and ``default`` items may be ``None`` to indicate
            they should be omitted.

    Returns:
        A string suitable for placement between the parentheses of a
        ``def`` statement (may be empty).

    Raises:
        ValueError: If a parameter has an invalid name, or a parameter without
            a default value follows one that has one.
    """
    rendered: List[str] = []
    seen_default = False
    seen_names: set = set()

    for index, param in enumerate(parameters):
        if not isinstance(param, tuple) or len(param) != 3:
            raise ValueError(
                f"Parameter at index {index} must be a (name, type, default) tuple, "
                f"got {param!r}"
            )

        name, annotation, default = param
        _validate_identifier(name, "parameter")

        if name in seen_names:
            raise ValueError(f"Duplicate parameter name: {name!r}")
        seen_names.add(name)

        piece = name
        if annotation:
            piece = f"{piece}: {annotation}"

        if default is not None:
            piece = f"{piece} = {default}" if annotation else f"{piece}={default}"
            seen_default = True
        elif seen_default:
            raise ValueError(
                f"Non-default parameter {name!r} follows a default parameter"
            )

        rendered.append(piece)

    return ", ".join(rendered)


def _format_docstring(docstring: str, indent: str) -> str:
    """Format a docstring using triple double-quotes and consistent indentation.

    Args:
        docstring: The docstring content (without surrounding quotes).
        indent: The indentation string applied to each line.

    Returns:
        The formatted docstring, ready to be embedded in a function body.
    """
    cleaned = textwrap.dedent(docstring).strip("\n")
    if "\n" not in cleaned:
        return f'{indent}"""{cleaned}"""'

    lines = cleaned.split("\n")
    body = "\n".join(f"{indent}{line}" if line else "" for line in lines)
    return f'{indent}"""\n{body}\n{indent}"""'


def build_python_function(
    name: str,
    parameters: Optional[Sequence[Parameter]] = None,
    return_type: Optional[str] = None,
    docstring: Optional[str] = None,
    body: Union[str, Iterable[str]] = "pass",
    decorators: Optional[Sequence[str]] = None,
    is_async: bool = False,
    indent: str = "    ",
) -> str:
    """Build the source code for a single Python function definition.

    Args:
        name: The function name. Must be a valid Python identifier.
        parameters: A sequence of ``(name, type_annotation, default)`` triples.
            Use ``None`` for the annotation or default when they are absent.
        return_type: Optional return type annotation (e.g. ``"int"``).
        docstring: Optional docstring text.
        body: Either a string containing the function body, or an iterable of
            lines. If empty, a ``pass`` statement is generated.
        decorators: Optional sequence of decorator expressions (without the
            leading ``@``).
        is_async: If ``True``, an ``async def`` is emitted.
        indent: The indentation string (defaults to four spaces).

    Returns:
        The generated function source as a string terminated by a newline.

    Raises:
        ValueError: If ``name`` is invalid, any parameter is malformed, or the
            resulting source code is not syntactically valid Python.
    """
    _validate_identifier(name, "function")

    params_text = _format_parameters(list(parameters or []))
    signature = f"{'async ' if is_async else ''}def {name}({params_text})"
    if return_type:
        signature = f"{signature} -> {return_type}"
    signature = f"{signature}:"

    lines: List[str] = []
    for decorator in decorators or []:
        decorator = decorator.strip()
        if not decorator:
            raise ValueError("Decorator expressions must be non-empty strings")
        lines.append(f"@{decorator.lstrip('@')}")
    lines.append(signature)

    if docstring:
        lines.append(_format_docstring(docstring, indent))

    if isinstance(body, str):
        body_text = textwrap.dedent(body).strip("\n")
    else:
        body_text = "\n".join(body).strip("\n")

    if not body_text:
        body_text = "pass"

    for body_line in body_text.split("\n"):
        lines.append(f"{indent}{body_line}" if body_line else "")

    source = "\n".join(lines) + "\n"

    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(
            f"Generated function source is not valid Python:\n{source}\n{exc}"
        ) from exc

    return source


def write_python_function(
    filename: PathLike,
    name: str,
    parameters: Optional[Sequence[Parameter]] = None,
    return_type: Optional[str] = None,
    docstring: Optional[str] = None,
    body: Union[str, Iterable[str]] = "pass",
    decorators: Optional[Sequence[str]] = None,
    is_async: bool = False,
    module_docstring: Optional[str] = None,
    imports: Optional[Sequence[str]] = None,
    overwrite: bool = True,
    encoding: str = "utf-8",
) -> Path:
    """Generate a Python function and write it to ``filename``.

    Args:
        filename: Path to the file that will receive the generated source.
        name: The function name.
        parameters: Sequence of ``(name, type_annotation, default)`` triples.
        return_type: Optional return type annotation.
        docstring: Optional function docstring.
        body: Function body as a string or iterable of source lines.
        decorators: Optional sequence of decorator expressions.
        is_async: If ``True``, produce an ``async def`` function.
        module_docstring: Optional module-level docstring inserted at the top.
        imports: Optional import statements written before the function.
        overwrite: If ``False`` and the target file already exists, raise
            :class:`FileExistsError`.
        encoding: Text encoding for the output file.

    Returns:
        The :class:`~pathlib.Path` of the written file.

    Raises:
        FileExistsError: If ``overwrite`` is ``False`` and the file exists.
        ValueError: If the generated source is invalid.
        OSError: If the file cannot be written.
    """
    path = Path(filename)

    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    parts: List[str] = []

    if module_docstring:
        cleaned = textwrap.dedent(module_docstring).strip("\n")
        parts.append(f'"""{cleaned}"""\n' if "\n" not in cleaned else f'"""\n{cleaned}\n"""\n')

    if imports:
        for statement in imports:
            statement = statement.strip()
            if not statement:
                continue
            parts.append(statement + "\n")
        parts.append("\n")

    function_source = build_python_function(
        name=name,
        parameters=parameters,
        return_type=return_type,
        docstring=docstring,
        body=body,
        decorators=decorators,
        is_async=is_async,
    )
    parts.append(function_source)

    contents = "".join(parts)

    # Final validation with all leading sections combined.
    try:
        ast.parse(contents)
    except SyntaxError as exc:
        raise ValueError(
            f"Generated module source is not valid Python:\n{contents}\n{exc}"
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding=encoding)
    return path


if __name__ == "__main__":  # pragma: no cover - demonstration only
    output = write_python_function(
        filename="generated_greet.py",
        name="greet",
        parameters=[("name", "str", None), ("greeting", "str", '"Hello"')],
        return_type="str",
        docstring="Return a friendly greeting for ``name``.",
        body="return f'{greeting}, {name}!'",
        module_docstring="Auto-generated greeting utilities.",
        imports=["from __future__ import annotations"],
    )
    print(f"Wrote generated function to {output.resolve()}")
