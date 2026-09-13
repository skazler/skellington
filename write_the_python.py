"""Utility module providing a robust implementation of common Python functions.

This module demonstrates production-quality Python code with full type hints,
Google-style docstrings, and comprehensive error handling.
"""

from __future__ import annotations

import logging
from functools import reduce
from typing import Callable, Iterable, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


def safe_divide(numerator: float, denominator: float) -> float:
    """Safely divide two numbers, guarding against division-by-zero errors.

    Args:
        numerator: The dividend value.
        denominator: The divisor value. Must be non-zero.

    Returns:
        The result of ``numerator / denominator`` as a float.

    Raises:
        TypeError: If either argument is not a numeric type (int or float).
        ZeroDivisionError: If ``denominator`` is zero.

    Example:
        >>> safe_divide(10, 2)
        5.0
    """
    if not isinstance(numerator, (int, float)) or isinstance(numerator, bool):
        raise TypeError(f"numerator must be int or float, got {type(numerator).__name__}")
    if not isinstance(denominator, (int, float)) or isinstance(denominator, bool):
        raise TypeError(f"denominator must be int or float, got {type(denominator).__name__}")
    if denominator == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return float(numerator) / float(denominator)


def chunk_sequence(sequence: Sequence[T], size: int) -> list[list[T]]:
    """Split a sequence into chunks of a given maximum size.

    Args:
        sequence: The input sequence to be chunked (e.g., list, tuple, str).
        size: The maximum size of each chunk. Must be a positive integer.

    Returns:
        A list of lists, where each inner list contains up to ``size`` items
        from the original ``sequence``. The final chunk may be smaller.

    Raises:
        TypeError: If ``size`` is not an integer.
        ValueError: If ``size`` is less than 1.

    Example:
        >>> chunk_sequence([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    if not isinstance(size, int) or isinstance(size, bool):
        raise TypeError(f"size must be an int, got {type(size).__name__}")
    if size < 1:
        raise ValueError(f"size must be a positive integer, got {size}")

    try:
        length = len(sequence)
    except TypeError as exc:
        raise TypeError("sequence must support len().") from exc

    return [list(sequence[i : i + size]) for i in range(0, length, size)]


def flatten(nested: Iterable[Iterable[T]]) -> list[T]:
    """Flatten a two-level nested iterable into a single flat list.

    Args:
        nested: An iterable whose items are themselves iterables.

    Returns:
        A single list containing all elements from all inner iterables,
        preserving order.

    Raises:
        TypeError: If ``nested`` or any of its elements are not iterable.

    Example:
        >>> flatten([[1, 2], [3, 4], [5]])
        [1, 2, 3, 4, 5]
    """
    if nested is None:
        raise TypeError("nested must be an iterable, got None")

    flat: list[T] = []
    try:
        for inner in nested:
            flat.extend(inner)
    except TypeError as exc:
        raise TypeError("All items in 'nested' must be iterable.") from exc
    return flat


def apply_pipeline(value: T, functions: Sequence[Callable[[T], T]]) -> T:
    """Apply a sequence of unary functions to an initial value in order.

    The output of each function is fed as the input to the next. Equivalent
    to ``fn(...f2(f1(value))...)``.

    Args:
        value: The initial value to transform.
        functions: An ordered sequence of callables, each taking one argument
            and returning a transformed value of the same type.

    Returns:
        The final transformed value after applying all functions.

    Raises:
        TypeError: If ``functions`` is not iterable or contains non-callables.
        RuntimeError: If any function in the pipeline raises an exception.

    Example:
        >>> apply_pipeline(3, [lambda x: x + 1, lambda x: x * 2])
        8
    """
    if functions is None:
        raise TypeError("functions must be a sequence of callables, got None")

    for index, func in enumerate(functions):
        if not callable(func):
            raise TypeError(f"Item at index {index} is not callable: {func!r}")

    def _apply(acc: T, func: Callable[[T], T]) -> T:
        try:
            return func(acc)
        except Exception as exc:  # noqa: BLE001 - re-raised with context
            logger.exception("Pipeline function %r failed.", func)
            raise RuntimeError(f"Pipeline function {func!r} failed: {exc}") from exc

    return reduce(_apply, functions, value)


def word_frequency(text: str, *, case_sensitive: bool = False) -> dict[str, int]:
    """Count occurrences of each whitespace-separated word in a string.

    Args:
        text: The input string to analyze.
        case_sensitive: If False (default), words are lowercased before
            counting so that "The" and "the" are treated as the same word.

    Returns:
        A dictionary mapping each unique word to its number of occurrences.

    Raises:
        TypeError: If ``text`` is not a string.

    Example:
        >>> word_frequency("the cat and the dog")
        {'the': 2, 'cat': 1, 'and': 1, 'dog': 1}
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")

    counts: dict[str, int] = {}
    for raw_word in text.split():
        word = raw_word if case_sensitive else raw_word.lower()
        counts[word] = counts.get(word, 0) + 1
    return counts


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("safe_divide(10, 4) = %s", safe_divide(10, 4))
    logger.info("chunk_sequence(range(7), 3) = %s", chunk_sequence(list(range(7)), 3))
    logger.info("flatten([[1, 2], [3]]) = %s", flatten([[1, 2], [3]]))
    logger.info(
        "apply_pipeline(5, [+1, *3, -2]) = %s",
        apply_pipeline(5, [lambda x: x + 1, lambda x: x * 3, lambda x: x - 2]),
    )
    logger.info("word_frequency('The the cat') = %s", word_frequency("The the cat"))
