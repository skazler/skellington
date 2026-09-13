"""Async demo application showcasing concurrency patterns.

This module demonstrates several core async/await patterns in Python:
    * Concurrent HTTP-like fetches using ``asyncio.gather``.
    * Producer/consumer pipeline via ``asyncio.Queue``.
    * Timeouts and cancellation handling.
    * Rate limiting with ``asyncio.Semaphore``.

Run the module directly to see the demo in action::

    $ python design_a_small.py
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("async_demo")


@dataclass(frozen=True)
class FetchResult:
    """Represents the result of a simulated fetch operation.

    Attributes:
        url: The (fake) URL that was fetched.
        status: An HTTP-like status code.
        elapsed: Time in seconds the fetch took.
        payload: The simulated response body.
    """

    url: str
    status: int
    elapsed: float
    payload: str


async def fake_fetch(url: str, *, min_delay: float = 0.2, max_delay: float = 1.5) -> FetchResult:
    """Simulate an asynchronous HTTP fetch.

    Args:
        url: The URL to "fetch".
        min_delay: Minimum simulated network delay in seconds.
        max_delay: Maximum simulated network delay in seconds.

    Returns:
        A :class:`FetchResult` describing the outcome.

    Raises:
        ValueError: If ``min_delay`` is negative or greater than ``max_delay``.
        RuntimeError: Occasionally simulated to demonstrate error handling.
    """
    if min_delay < 0 or min_delay > max_delay:
        raise ValueError("Invalid delay bounds.")

    delay = random.uniform(min_delay, max_delay)
    start = time.perf_counter()
    await asyncio.sleep(delay)
    elapsed = time.perf_counter() - start

    # Simulate occasional failures (~10% of calls).
    if random.random() < 0.10:
        raise RuntimeError(f"Simulated network failure for {url}")

    return FetchResult(
        url=url,
        status=200,
        elapsed=elapsed,
        payload=f"<html>content of {url}</html>",
    )


async def fetch_all(urls: Iterable[str], *, concurrency: int = 5) -> List[FetchResult]:
    """Fetch many URLs concurrently with a bounded level of parallelism.

    Args:
        urls: An iterable of URLs to fetch.
        concurrency: Maximum number of concurrent fetches.

    Returns:
        A list of successful :class:`FetchResult` objects. Failures are
        logged and skipped rather than raised.
    """
    if concurrency <= 0:
        raise ValueError("concurrency must be a positive integer")

    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_fetch(url: str) -> Optional[FetchResult]:
        async with semaphore:
            try:
                result = await asyncio.wait_for(fake_fetch(url), timeout=2.0)
                logger.info("OK   %-25s (%.2fs)", url, result.elapsed)
                return result
            except asyncio.TimeoutError:
                logger.warning("TIMEOUT %s", url)
            except RuntimeError as exc:
                logger.error("FAIL %s -> %s", url, exc)
            return None

    results = await asyncio.gather(*(_bounded_fetch(u) for u in urls))
    return [r for r in results if r is not None]


async def producer(queue: "asyncio.Queue[Optional[int]]", count: int) -> None:
    """Produce ``count`` items and enqueue them, then signal completion.

    Args:
        queue: The shared asyncio queue.
        count: Number of items to produce.
    """
    for i in range(1, count + 1):
        await asyncio.sleep(random.uniform(0.05, 0.25))
        logger.info("produced item %d", i)
        await queue.put(i)
    await queue.put(None)  # sentinel to signal shutdown


async def consumer(name: str, queue: "asyncio.Queue[Optional[int]]") -> int:
    """Consume items until a ``None`` sentinel is received.

    Args:
        name: Human-readable consumer name (for logging).
        queue: The shared asyncio queue.

    Returns:
        The number of items processed by this consumer.
    """
    processed = 0
    while True:
        item = await queue.get()
        try:
            if item is None:
                # Re-post sentinel so sibling consumers also stop.
                await queue.put(None)
                return processed
            await asyncio.sleep(random.uniform(0.1, 0.4))
            logger.info("%s consumed item %d", name, item)
            processed += 1
        finally:
            queue.task_done()


async def run_pipeline(items: int = 8, consumers: int = 3) -> None:
    """Run a producer/consumer pipeline demo.

    Args:
        items: Number of items the producer will emit.
        consumers: Number of concurrent consumer tasks.
    """
    queue: asyncio.Queue[Optional[int]] = asyncio.Queue(maxsize=4)
    producer_task = asyncio.create_task(producer(queue, items))
    consumer_tasks = [asyncio.create_task(consumer(f"C{i+1}", queue)) for i in range(consumers)]

    await producer_task
    totals = await asyncio.gather(*consumer_tasks)
    logger.info("pipeline complete: %s", dict(zip((f"C{i+1}" for i in range(consumers)), totals)))


async def time_it(label: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Time an awaitable and log the elapsed duration.

    Args:
        label: A short label identifying the section being timed.
        coro_factory: A zero-argument callable returning an awaitable.
    """
    logger.info("=== %s: start ===", label)
    start = time.perf_counter()
    try:
        await coro_factory()
    except Exception:  # noqa: BLE001 - top-level demo boundary
        logger.exception("%s failed", label)
    finally:
        logger.info("=== %s: done in %.2fs ===\n", label, time.perf_counter() - start)


async def main() -> None:
    """Entry point that runs the full async demo."""
    random.seed(42)

    urls = [f"https://example.com/page/{i}" for i in range(1, 11)]

    async def _fetch_demo() -> None:
        results = await fetch_all(urls, concurrency=4)
        logger.info("fetched %d/%d URLs successfully", len(results), len(urls))

    await time_it("Concurrent Fetch Demo", _fetch_demo)
    await time_it("Producer/Consumer Demo", lambda: run_pipeline(items=8, consumers=3))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user; shutting down.")
