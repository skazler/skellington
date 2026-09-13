"""Utility module demonstrating docstrings and basic input validation.

This module provides a small example function that computes the arithmetic
mean of a sequence of numeric values. It illustrates best practices for
writing Google-style docstrings and validating user-supplied input.
"""

from __future__ import annotations

from numbers import Real
from typing import Iterable, Sequence, Union

Number = Union[int, float]


def compute_average(values: Iterable[Number]) -> float:
    """Compute the arithmetic mean of a sequence of numeric values.

    The function accepts any iterable of real numbers (``int`` or ``float``)
    and returns their arithmetic mean as a ``float``. Booleans are rejected
    even though they are technically a subclass of ``int`` in Python,
    because treating them as numeric values is almost always a bug.

    Args:
        values: An iterable containing the numeric values to average.
            The iterable must be non-empty and every element must be a
            real number (``int`` or ``float``, excluding ``bool``).

    Returns:
        The arithmetic mean of ``values`` as a ``float``.

    Raises:
        TypeError: If ``values`` is not iterable, or if any element in
            ``values`` is not a real number.
        ValueError: If ``values`` is empty.

    Example:
        >>> compute_average([1, 2, 3, 4])
        2.5
        >>> compute_average((10.0, 20.0))
        15.0
    """
    # Validate that ``values`` is iterable but not a string/bytes object,
    # which would otherwise iterate character-by-character and produce
    # confusing error messages.
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(
            f"'values' must be an iterable of numbers, not {type(values).__name__}"
        )

    try:
        iterator = iter(values)
    except TypeError as exc:
        raise TypeError(
            f"'values' must be iterable, got {type(values).__name__}"
        ) from exc

    # Materialize the iterable so we can validate elements and compute
    # length without consuming a one-shot generator twice.
    materialized: Sequence[Number] = list(iterator)

    if not materialized:
        raise ValueError("'values' must contain at least one element")

    for index, item in enumerate(materialized):
        if isinstance(item, bool) or not isinstance(item, Real):
            raise TypeError(
                f"All elements of 'values' must be real numbers; "
                f"element at index {index} is {type(item).__name__}"
            )

    total: float = float(sum(materialized))
    return total / len(materialized)


if __name__ == "__main__":
    sample_values: list[Number] = [10, 20, 30, 40, 50]
    print(f"Average of {sample_values} = {compute_average(sample_values)}")
