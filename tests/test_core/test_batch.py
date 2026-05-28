"""Tests for the Anthropic Batch API primitive."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from skellington.core.batch import (
    AnthropicBatchClient,
    BatchError,
    _build_params,
    _custom_id,
    _index_from_custom_id,
)
from skellington.core.types import LLMConfig, Message, MessageRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(monkeypatch) -> AnthropicBatchClient:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    from skellington.core import config as config_module

    config_module.get_settings.cache_clear()
    client = AnthropicBatchClient()
    client._client = MagicMock()
    return client


def _stub_text_message(text: str = "hi", model: str = "claude-opus-4-7"):
    """Build an anthropic-shaped message reply for batch results."""
    msg = MagicMock()
    msg.model = model
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 5
    msg.usage.output_tokens = 3
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    msg.content = [text_block]
    return msg


def _stub_result_entry(custom_id: str, *, succeeded: bool = True, text: str = "ok"):
    entry = MagicMock()
    entry.custom_id = custom_id
    if succeeded:
        entry.result.type = "succeeded"
        entry.result.message = _stub_text_message(text)
    else:
        entry.result.type = "errored"
        entry.result.error = "synthetic failure"
    return entry


class _AsyncIter:
    """Async iterator over a fixed list — for messages.batches.results() stub."""

    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


# ---------------------------------------------------------------------------
# Custom ID helpers
# ---------------------------------------------------------------------------


def test_custom_id_round_trip():
    assert _index_from_custom_id(_custom_id(0)) == 0
    assert _index_from_custom_id(_custom_id(42)) == 42


def test_index_from_custom_id_rejects_bad_format():
    with pytest.raises(ValueError):
        _index_from_custom_id("not-a-skel-id")


# ---------------------------------------------------------------------------
# Param translation
# ---------------------------------------------------------------------------


def test_build_params_adds_cache_control_for_caching_models():
    cfg = LLMConfig(model="claude-opus-4-7", system_prompt="be helpful")
    params = _build_params([Message(role=MessageRole.USER, content="hi")], cfg)

    assert isinstance(params["system"], list)
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_build_params_includes_thinking_when_requested_and_supported():
    cfg = LLMConfig(model="claude-opus-4-7", prefer_thinking=True)
    params = _build_params([Message(role=MessageRole.USER, content="hi")], cfg)

    assert params["thinking"] == {"type": "enabled", "budget_tokens": 4096}


def test_build_params_skips_thinking_when_unsupported():
    # Haiku currently has supports_thinking=False in the registry
    cfg = LLMConfig(model="claude-haiku-4-5-20251001", prefer_thinking=True)
    params = _build_params([Message(role=MessageRole.USER, content="hi")], cfg)

    assert "thinking" not in params


# ---------------------------------------------------------------------------
# submit()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_returns_batch_id_and_sends_correct_requests(monkeypatch):
    client = _make_client(monkeypatch)
    mock_batch = MagicMock(id="batch_xyz")
    client._client.messages.batches.create = AsyncMock(return_value=mock_batch)

    calls = [
        ([Message(role=MessageRole.USER, content="one")], LLMConfig(model="claude-opus-4-7")),
        ([Message(role=MessageRole.USER, content="two")], LLMConfig(model="claude-opus-4-7")),
    ]
    batch_id = await client.submit(calls)

    assert batch_id == "batch_xyz"
    sent = client._client.messages.batches.create.call_args.kwargs["requests"]
    assert len(sent) == 2
    assert sent[0]["custom_id"] == "skel-0"
    assert sent[1]["custom_id"] == "skel-1"
    assert sent[0]["params"]["messages"][0]["content"] == "one"


@pytest.mark.asyncio
async def test_submit_rejects_models_without_batch_support(monkeypatch):
    client = _make_client(monkeypatch)

    calls = [([Message(role=MessageRole.USER, content="x")], LLMConfig(model="gpt-4o"))]
    with pytest.raises(ValueError, match="does not support the Anthropic Batch API"):
        await client.submit(calls)


@pytest.mark.asyncio
async def test_submit_rejects_empty_call_list(monkeypatch):
    client = _make_client(monkeypatch)

    with pytest.raises(ValueError, match="at least one call"):
        await client.submit([])


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_reports_counts_and_processing_status(monkeypatch):
    client = _make_client(monkeypatch)
    batch = MagicMock(id="batch_xyz", processing_status="in_progress")
    batch.request_counts.processing = 5
    batch.request_counts.succeeded = 0
    batch.request_counts.errored = 0
    batch.request_counts.canceled = 0
    batch.request_counts.expired = 0
    client._client.messages.batches.retrieve = AsyncMock(return_value=batch)

    info = await client.status("batch_xyz")

    assert info["id"] == "batch_xyz"
    assert info["processing_status"] == "in_progress"
    assert info["request_counts"]["processing"] == 5


# ---------------------------------------------------------------------------
# collect()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_preserves_submission_order(monkeypatch):
    client = _make_client(monkeypatch)
    ended_batch = MagicMock(processing_status="ended")
    client._client.messages.batches.retrieve = AsyncMock(return_value=ended_batch)

    # Return results out of order — collect() should reorder them
    client._client.messages.batches.results = AsyncMock(
        return_value=_AsyncIter(
            [
                _stub_result_entry("skel-2", text="third"),
                _stub_result_entry("skel-0", text="first"),
                _stub_result_entry("skel-1", text="second"),
            ]
        )
    )

    responses = await client.collect("batch_xyz")

    assert [r.content for r in responses] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_collect_raises_batcherror_on_failed_entry(monkeypatch):
    client = _make_client(monkeypatch)
    ended = MagicMock(processing_status="ended")
    client._client.messages.batches.retrieve = AsyncMock(return_value=ended)
    client._client.messages.batches.results = AsyncMock(
        return_value=_AsyncIter(
            [
                _stub_result_entry("skel-0", text="ok"),
                _stub_result_entry("skel-1", succeeded=False),
            ]
        )
    )

    with pytest.raises(BatchError, match="errored"):
        await client.collect("batch_xyz")


@pytest.mark.asyncio
async def test_collect_refuses_unended_batch(monkeypatch):
    client = _make_client(monkeypatch)
    in_progress = MagicMock(processing_status="in_progress")
    client._client.messages.batches.retrieve = AsyncMock(return_value=in_progress)

    with pytest.raises(RuntimeError, match="not ended"):
        await client.collect("batch_xyz")


# ---------------------------------------------------------------------------
# submit_and_wait()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_and_wait_polls_until_ended_then_collects(monkeypatch):
    client = _make_client(monkeypatch)
    client._client.messages.batches.create = AsyncMock(return_value=MagicMock(id="b"))

    # First retrieve: in_progress. Second retrieve: ended. Third retrieve (in collect): ended.
    in_progress = MagicMock(processing_status="in_progress")
    in_progress.request_counts.processing = 1
    in_progress.request_counts.succeeded = 0
    in_progress.request_counts.errored = 0
    in_progress.request_counts.canceled = 0
    in_progress.request_counts.expired = 0

    ended = MagicMock(processing_status="ended")
    ended.request_counts.processing = 0
    ended.request_counts.succeeded = 1
    ended.request_counts.errored = 0
    ended.request_counts.canceled = 0
    ended.request_counts.expired = 0

    client._client.messages.batches.retrieve = AsyncMock(side_effect=[in_progress, ended, ended])
    client._client.messages.batches.results = AsyncMock(
        return_value=_AsyncIter([_stub_result_entry("skel-0", text="done")])
    )

    responses = await client.submit_and_wait(
        [([Message(role=MessageRole.USER, content="q")], LLMConfig(model="claude-opus-4-7"))],
        poll_interval_s=0,  # speed up the test
    )

    assert len(responses) == 1
    assert responses[0].content == "done"


@pytest.mark.asyncio
async def test_submit_and_wait_times_out_if_batch_never_ends(monkeypatch):
    client = _make_client(monkeypatch)
    client._client.messages.batches.create = AsyncMock(return_value=MagicMock(id="b"))

    in_progress = MagicMock(processing_status="in_progress")
    in_progress.request_counts.processing = 1
    in_progress.request_counts.succeeded = 0
    in_progress.request_counts.errored = 0
    in_progress.request_counts.canceled = 0
    in_progress.request_counts.expired = 0
    client._client.messages.batches.retrieve = AsyncMock(return_value=in_progress)

    with pytest.raises(TimeoutError):
        await client.submit_and_wait(
            [([Message(role=MessageRole.USER, content="q")], LLMConfig(model="claude-opus-4-7"))],
            poll_interval_s=0,
            timeout_s=0.05,
        )
