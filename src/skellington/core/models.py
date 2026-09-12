"""
Model registry — capability flags keyed by model ID.

Each flag exists to gate a specific prompt fragment or behavior. Add a flag
only when you have a concrete adaptation that depends on it; otherwise the
flag is dead weight that drifts from reality.
"""

from __future__ import annotations

from typing import Literal

import structlog
from pydantic import BaseModel

from skellington.core.types import LLMProvider

logger = structlog.get_logger(__name__)


class ModelCard(BaseModel):
    """Capabilities of a single model. Drives prompt assembly and request shaping."""

    id: str
    provider: LLMProvider
    context_window: int

    supports_native_json: bool = False
    prefers_xml_tags: bool = False
    supports_parallel_tools: bool = True
    max_parallel_tools: int = 8
    supports_thinking: bool = False
    supports_prompt_caching: bool = False
    supports_batch_api: bool = False

    supports_sampling_params: bool = False
    """Whether temperature / top_p / top_k are accepted.

    Off by default because no current Anthropic model takes them: they were
    removed from the API on Opus 4.7 and later, and the installed SDK has no
    such parameter on messages.create() for any model. OpenAI still does.

    There is no replacement for pinning randomness. `effort` tunes depth and
    cost, not determinism, so a run on a current Anthropic model cannot be
    made reproducible by configuration.
    """

    thinking_style: Literal["budget", "adaptive"] = "adaptive"
    """How to ask for extended thinking.

    "budget" is the pre-4.7 form, {"type": "enabled", "budget_tokens": N}.
    "adaptive" is {"type": "adaptive"} — budget_tokens returns a 400 on 4.7
    and later. Only consulted when supports_thinking is set.
    """

    supports_effort: bool = False
    """Whether output_config.effort is accepted (low/medium/high/xhigh/max)."""


MODELS: dict[str, ModelCard] = {
    "claude-opus-4-7": ModelCard(
        id="claude-opus-4-7",
        provider=LLMProvider.ANTHROPIC,
        context_window=1_000_000,
        prefers_xml_tags=True,
        supports_thinking=True,
        thinking_style="adaptive",
        supports_effort=True,
        supports_prompt_caching=True,
        supports_batch_api=True,
    ),
    "claude-sonnet-4-6": ModelCard(
        id="claude-sonnet-4-6",
        provider=LLMProvider.ANTHROPIC,
        context_window=1_000_000,
        prefers_xml_tags=True,
        supports_thinking=True,
        thinking_style="adaptive",
        supports_effort=True,
        supports_prompt_caching=True,
        supports_batch_api=True,
    ),
    "claude-haiku-4-5": ModelCard(
        id="claude-haiku-4-5",
        provider=LLMProvider.ANTHROPIC,
        context_window=200_000,
        prefers_xml_tags=True,
        supports_prompt_caching=True,
        supports_batch_api=True,
    ),
    "gpt-4o": ModelCard(
        id="gpt-4o",
        provider=LLMProvider.OPENAI,
        context_window=128_000,
        supports_native_json=True,
        supports_sampling_params=True,
    ),
    "gpt-4o-mini": ModelCard(
        id="gpt-4o-mini",
        provider=LLMProvider.OPENAI,
        context_window=128_000,
        supports_native_json=True,
        supports_sampling_params=True,
        max_parallel_tools=4,
    ),
}


_FALLBACK = ModelCard(
    id="__unknown__",
    provider=LLMProvider.ANTHROPIC,
    context_window=32_000,
    supports_parallel_tools=False,
    max_parallel_tools=1,
)


def get_model_card(model_id: str) -> ModelCard:
    """Look up a model's capabilities, returning a conservative fallback if unknown."""
    card = MODELS.get(model_id)
    if card is not None:
        return card
    logger.warning("unknown model, using conservative fallback", model_id=model_id)
    return _FALLBACK.model_copy(update={"id": model_id})
