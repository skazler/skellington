"""String reversal utilities.

This module provides multiple implementations of string reversal in Python,
including an idiomatic slice-based approach, an iterative approach, and a
recursive approach. It also exposes a small command-line interface for
quickly reversing strings passed as arguments.
"""

from __future__ import annotations

import sys
from typing import List


def reverse_string(text: str) -> str:
    """Reverse a string using Python's slice notation.

    This is the most idiomatic and performant way to reverse a string in
    Python. It creates a new string containing the characters of ``text``
    in reverse order.

    Args:
        text: The input string to reverse.

    Returns:
        A new string that is the reverse of ``text``.

    Raises:
        TypeError: If ``text`` is not an instance of ``str``.

    Example:
        >>> reverse_string("hello")
        'olleh'
        >>> reverse_string("")
        ''
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Expected 'text' to be of type str, got {type(text).__name__}"
        )
    return text[::-1]


def reverse_string_iterative(text: str) -> str:
    """Reverse a string iteratively by building it character by character.

    Uses a list as a mutable buffer to avoid the quadratic cost of repeated
    string concatenation, then joins the buffer at the end.

    Args:
        text: The input string to reverse.

    Returns:
        A new string that is the reverse of ``text``.

    Raises:
        TypeError: If ``text`` is not an instance of ``str``.

    Example:
        >>> reverse_string_iterative("abc")
        'cba'
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Expected 'text' to be of type str, got {type(text).__name__}"
        )

    buffer: List[str] = []
    for index in range(len(text) - 1, -1, -1):
        buffer.append(text[index])
    return "".join(buffer)


def reverse_string_recursive(text: str) -> str:
    """Reverse a string using recursion.

    Note:
        Python's default recursion limit (typically 1000) means this
        implementation is unsuitable for very long strings. Prefer
        :func:`reverse_string` for production use.

    Args:
        text: The input string to reverse.

    Returns:
        A new string that is the reverse of ``text``.

    Raises:
        TypeError: If ``text`` is not an instance of ``str``.
        RecursionError: If ``text`` is longer than the interpreter's
            recursion limit allows.

    Example:
        >>> reverse_string_recursive("python")
        'nohtyp'
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Expected 'text' to be of type str, got {type(text).__name__}"
        )
    if len(text) <= 1:
        return text
    return reverse_string_recursive(text[1:]) + text[0]


def main(argv: List[str]) -> int:
    """Command-line entry point for reversing strings.

    Reads each command-line argument, reverses it using :func:`reverse_string`,
    and prints the result to standard output. If no arguments are provided,
    reads a single line from standard input.

    Args:
        argv: The list of command-line arguments (excluding the program name).

    Returns:
        An exit code: ``0`` on success, ``1`` on error.
    """
    try:
        if argv:
            for token in argv:
                print(reverse_string(token))
        else:
            line = sys.stdin.readline().rstrip("\n")
            print(reverse_string(line))
    except (TypeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
