"""
Anthropic Message Batches API wrapper.

The Batch API trades latency for cost: 50% off vs sync pricing with a 24h SLA.
Up to 100k requests per batch. Useful for bulk-processing many INDEPENDENT
requests (e.g. scoring a backlog, nightly analysis) — not for low-latency
interactive use.

Scope of this module: the primitive only. Submit a list of calls, poll, get
results. Integrating batch into the realtime Orchestrator is a separate
concern; see [BatchOrchestrator](orchestrator_batch.py) for an
opinionated wrapper, or use this primitive directly for custom bulk jobs.
"""

from __future__ import annotations

import asyncio
from typing import Iterable

import anthropic
import structlog

from skellington.core.config import get_settings
from skellington.core.models import get_model_card
from skellington.core.types import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)

logger = structlog.get_logger(__name__)


# The Anthropic Batch API uses our custom_id to correlate results back to
# requests. We mint sequential ids so the caller can also restore order.
_CUSTOM_ID_PREFIX = "skel-"


BatchCall = tuple[list[Message], LLMConfig]


class BatchError(RuntimeError):
    """A batch entry came back as errored / expired / canceled."""


class AnthropicBatchClient:
    """Wraps anthropic.messages.batches for bulk processing.

    Typical use:
        client = AnthropicBatchClient()
        results = await client.submit_and_wait([
            ([Message(role=USER, content="question 1")], LLMConfig(model="claude-haiku-...")),
            ([Message(role=USER, content="question 2")], LLMConfig(model="claude-haiku-...")),
        ])

    For long-running jobs where you want to check back later instead of
    polling, use submit() + status() + collect() directly.
    """

    provider = LLMProvider.ANTHROPIC

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # ------------------------------------------------------------------
    # Low-level: submit / status / collect
    # ------------------------------------------------------------------

    async def submit(self, calls: list[BatchCall]) -> str:
        """Submit a batch. Returns the batch id. Does not wait."""
        if not calls:
            raise ValueError("submit() requires at least one call")

        for _, config in calls:
            card = get_model_card(config.model)
            if not card.supports_batch_api:
                raise ValueError(
                    f"model {config.model!r} does not support the Anthropic Batch API; "
                    "use a Claude model with supports_batch_api=True in its ModelCard"
                )

        requests = [
            {"custom_id": _custom_id(i), "params": _build_params(messages, config)}
            for i, (messages, config) in enumerate(calls)
        ]
        logger.info("submitting batch", size=len(requests))
        batch = await self._client.messages.batches.create(requests=requests)
        logger.info("batch submitted", batch_id=batch.id)
        return batch.id

    async def status(self, batch_id: str) -> dict:
        """Return the current status of a batch (processing_status + counts)."""
        batch = await self._client.messages.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "processing_status": batch.processing_status,
            "request_counts": {
                "processing": batch.request_counts.processing,
                "succeeded": batch.request_counts.succeeded,
                "errored": batch.request_counts.errored,
                "canceled": batch.request_counts.canceled,
                "expired": batch.request_counts.expired,
            },
        }

    async def collect(self, batch_id: str) -> list[LLMResponse]:
        """Fetch results of an ended batch. Returns responses in original submission order.

        Raises BatchError if any entry errored / expired / was canceled.
        Raises RuntimeError if the batch hasn't ended yet.
        """
        batch = await self._client.messages.batches.retrieve(batch_id)
        if batch.processing_status != "ended":
            raise RuntimeError(
                f"batch {batch_id} is not ended (status={batch.processing_status}); "
                "use submit_and_wait() or poll status() first"
            )

        by_index: dict[int, LLMResponse] = {}
        async for entry in await self._client.messages.batches.results(batch_id):
            index = _index_from_custom_id(entry.custom_id)
            result_type = entry.result.type
            if result_type == "succeeded":
                by_index[index] = _parse_succeeded(entry.result.message)
            else:
                # errored / canceled / expired all surface here.
                raise BatchError(
                    f"batch entry {entry.custom_id} failed with type={result_type}: "
                    f"{getattr(entry.result, 'error', None)}"
                )

        return [by_index[i] for i in sorted(by_index)]

    # ------------------------------------------------------------------
    # High-level: submit + poll + collect
    # ------------------------------------------------------------------

    async def submit_and_wait(
        self,
        calls: list[BatchCall],
        *,
        poll_interval_s: float = 30.0,
        timeout_s: float = 86_400.0,
    ) -> list[LLMResponse]:
        """Submit a batch and block until results are ready.

        Args:
            poll_interval_s: how often to check batch status. Anthropic's
                rate limit on /retrieve is generous; 30s is conservative.
            timeout_s: give up after this long. Anthropic's SLA is 24h.

        Raises TimeoutError if the batch doesn't end within timeout_s.
        """
        batch_id = await self.submit(calls)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_s

        while loop.time() < deadline:
            current = await self.status(batch_id)
            if current["processing_status"] == "ended":
                return await self.collect(batch_id)
            await asyncio.sleep(poll_interval_s)

        raise TimeoutError(f"batch {batch_id} did not end within {timeout_s}s")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _custom_id(index: int) -> str:
    return f"{_CUSTOM_ID_PREFIX}{index}"


def _index_from_custom_id(custom_id: str) -> int:
    if not custom_id.startswith(_CUSTOM_ID_PREFIX):
        raise ValueError(f"unexpected custom_id format: {custom_id!r}")
    return int(custom_id[len(_CUSTOM_ID_PREFIX) :])


def _build_params(messages: list[Message], config: LLMConfig) -> dict:
    """Translate Skellington's LLMConfig + Messages into Anthropic's params shape.

    Mirrors AnthropicClient.complete() so batch results match what you'd
    get from a sync call — same caching, same thinking, same system block shape.
    """
    card = get_model_card(config.model)

    conversation = [
        {"role": m.role.value, "content": m.content}
        for m in messages
        if m.role != MessageRole.SYSTEM
    ]

    params: dict = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "messages": conversation,
    }

    if config.system_prompt:
        if card.supports_prompt_caching:
            params["system"] = [
                {
                    "type": "text",
                    "text": config.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            params["system"] = config.system_prompt

    if config.tools:
        params["tools"] = config.tools

    if config.prefer_thinking and card.supports_thinking:
        params["thinking"] = {
            "type": "enabled",
            "budget_tokens": config.thinking_budget_tokens,
        }

    return params


def _parse_succeeded(message) -> LLMResponse:
    """Convert a successful batch entry's message into our LLMResponse."""
    tool_calls: list[ToolCall] = []
    text_content = ""
    for block in message.content:
        if block.type == "text":
            text_content += block.text
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

    return LLMResponse(
        content=text_content,
        model=message.model,
        provider=LLMProvider.ANTHROPIC,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        tool_calls=tool_calls,
        stop_reason=message.stop_reason or "end_turn",
    )
