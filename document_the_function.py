"""Demonstration module showing how to document Python functions.

This module provides well-documented example functions that illustrate
Google-style docstrings, including type hints, argument descriptions,
return values, raised exceptions, and runnable examples.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

Number = Union[int, float]


def calculate_average(values: Sequence[Number]) -> float:
    """Calculate the arithmetic mean of a sequence of numbers.

    The arithmetic mean is defined as the sum of the values divided by
    the number of values. This function accepts any non-empty sequence
    of ``int`` or ``float`` values and returns the mean as a ``float``.

    Args:
        values: A non-empty sequence of numeric values (``int`` or
            ``float``) whose average will be computed.

    Returns:
        The arithmetic mean of ``values`` as a ``float``.

    Raises:
        TypeError: If ``values`` is not a sequence or contains a
            non-numeric element.
        ValueError: If ``values`` is empty.

    Examples:
        Basic usage with a list of integers::

            >>> calculate_average([1, 2, 3, 4, 5])
            3.0

        Usage with a tuple of floats::

            >>> calculate_average((2.5, 3.5, 4.0))
            3.3333333333333335

        Raising ``ValueError`` for empty input::

            >>> calculate_average([])
            Traceback (most recent call last):
                ...
            ValueError: 'values' must contain at least one element.
    """
    if not isinstance(values, Sequence):
        raise TypeError(
            f"'values' must be a Sequence, got {type(values).__name__}."
        )
    if len(values) == 0:
        raise ValueError("'values' must contain at least one element.")

    total: float = 0.0
    for index, item in enumerate(values):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"Element at index {index} is not numeric: "
                f"{item!r} ({type(item).__name__})."
            )
        total += float(item)

    return total / len(values)


def filter_positive(values: Iterable[Number]) -> List[Number]:
    """Return a list containing only the strictly positive values.

    Args:
        values: An iterable of numeric values (``int`` or ``float``).

    Returns:
        A new list containing only elements ``x`` such that ``x > 0``,
        preserving their original order.

    Raises:
        TypeError: If any element in ``values`` is not numeric.

    Examples:
        >>> filter_positive([-2, -1, 0, 1, 2])
        [1, 2]
        >>> filter_positive([0.0, 0.5, -3.1, 4])
        [0.5, 4]
        >>> filter_positive([])
        []
    """
    result: List[Number] = []
    for index, item in enumerate(values):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"Element at index {index} is not numeric: "
                f"{item!r} ({type(item).__name__})."
            )
        if item > 0:
            result.append(item)
    return result


def greet(name: str, greeting: str = "Hello") -> str:
    """Build a friendly greeting message.

    Args:
        name: The name of the person or entity to greet. Must be a
            non-empty string after stripping whitespace.
        greeting: The greeting phrase to prepend. Defaults to ``"Hello"``.

    Returns:
        A greeting string of the form ``"{greeting}, {name}!"``.

    Raises:
        TypeError: If ``name`` or ``greeting`` is not a ``str``.
        ValueError: If ``name`` is empty or only whitespace.

    Examples:
        >>> greet("Alice")
        'Hello, Alice!'
        >>> greet("Bob", greeting="Hi")
        'Hi, Bob!'
    """
    if not isinstance(name, str):
        raise TypeError(f"'name' must be a str, got {type(name).__name__}.")
    if not isinstance(greeting, str):
        raise TypeError(
            f"'greeting' must be a str, got {type(greeting).__name__}."
        )
    if not name.strip():
        raise ValueError("'name' must not be empty or whitespace only.")

    return f"{greeting}, {name}!"


if __name__ == "__main__":
    import doctest

    failures, tests = doctest.testmod(verbose=True)
    print(f"\nRan {tests} doctests with {failures} failure(s).")
