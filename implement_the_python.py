"""Utility module providing a robust implementation of a Python function.

This module demonstrates production-quality Python code including full type
hints, Google-style docstrings, proper error handling, and a runnable
demonstration in the ``__main__`` block.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Sequence, Union

__all__ = ["calculate_statistics", "Number"]

logger = logging.getLogger(__name__)

Number = Union[int, float]


def calculate_statistics(values: Iterable[Number]) -> dict[str, float]:
    """Compute basic descriptive statistics for a sequence of numbers.

    The function accepts any iterable of numeric values and returns a
    dictionary containing the count, sum, mean, minimum, maximum, and
    (population) variance of the input.

    Args:
        values: An iterable of ``int`` or ``float`` values. The iterable
            must contain at least one element and must not contain any
            non-numeric items.

    Returns:
        A dictionary mapping statistic names to their computed float
        values. Keys are: ``count``, ``sum``, ``mean``, ``min``, ``max``,
        and ``variance``.

    Raises:
        TypeError: If ``values`` is not iterable, or if any element is
            not a real number (``bool`` values are also rejected).
        ValueError: If ``values`` is empty.

    Example:
        >>> stats = calculate_statistics([1, 2, 3, 4, 5])
        >>> stats["mean"]
        3.0
        >>> stats["count"]
        5.0
    """
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise TypeError(
            f"Expected an iterable of numbers, got {type(values).__name__!r}"
        ) from exc

    numeric_values: List[float] = []
    for index, item in enumerate(iterator):
        # Explicitly reject bool because ``bool`` is a subclass of ``int``
        # in Python, which is almost never desired for numeric statistics.
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"Element at index {index} is not a real number: "
                f"{item!r} (type {type(item).__name__})"
            )
        numeric_values.append(float(item))

    if not numeric_values:
        raise ValueError("Cannot compute statistics on an empty iterable.")

    count: int = len(numeric_values)
    total: float = sum(numeric_values)
    mean: float = total / count
    minimum: float = min(numeric_values)
    maximum: float = max(numeric_values)
    variance: float = sum((x - mean) ** 2 for x in numeric_values) / count

    logger.debug(
        "Computed statistics: count=%d, mean=%.6f, variance=%.6f",
        count,
        mean,
        variance,
    )

    return {
        "count": float(count),
        "sum": total,
        "mean": mean,
        "min": minimum,
        "max": maximum,
        "variance": variance,
    }


def _demo(sample: Sequence[Number]) -> None:
    """Run a demonstration of :func:`calculate_statistics`.

    Args:
        sample: A sequence of numeric values used for the demo.
    """
    print(f"Input sample: {list(sample)}")
    stats = calculate_statistics(sample)
    for name, value in stats.items():
        print(f"  {name:<8} = {value:.4f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    _demo([2, 4, 4, 4, 5, 5, 7, 9])
