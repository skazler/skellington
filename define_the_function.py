"""Module defining a function signature for reversing a string.

This module provides a well-typed, documented function that accepts a single
string parameter and returns its reversed form. It is intended as a small,
reusable utility with strict input validation.
"""

from __future__ import annotations


def reverse_string(text: str) -> str:
    """Reverse the characters of the given string.

    This function takes a single string as input and returns a new string
    whose characters appear in the opposite order. The original string is
    not modified (strings are immutable in Python).

    Args:
        text: The string to reverse. Must be an instance of ``str``.
            An empty string is allowed and will simply return an empty
            string.

    Returns:
        A new string containing the characters of ``text`` in reverse order.

    Raises:
        TypeError: If ``text`` is not an instance of ``str``.

    Example:
        >>> reverse_string("hello")
        'olleh'
        >>> reverse_string("")
        ''
        >>> reverse_string("A man a plan a canal Panama")
        'amanaP lanac a nalp a nam A'
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Expected 'text' to be of type 'str', got '{type(text).__name__}'."
        )

    return text[::-1]


if __name__ == "__main__":
    sample: str = "Hello, World!"
    print(f"Original: {sample}")
    print(f"Reversed: {reverse_string(sample)}")
