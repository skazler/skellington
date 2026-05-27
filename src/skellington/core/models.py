"""
Model registry — capability flags keyed by model ID.

Each flag exists to gate a specific prompt fragment or behavior. Add a flag
only when you have a concrete adaptation that depends on it; otherwise the
flag is dead weight that drifts from reality.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

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


MODELS: dict[str, ModelCard] = {
    "claude-opus-4-7": ModelCard(
        id="claude-opus-4-7",
        provider=LLMProvider.ANTHROPIC,
        context_window=200_000,
        prefers_xml_tags=True,
        supports_thinking=True,
        supports_prompt_caching=True,
    ),
    "claude-sonnet-4-6": ModelCard(
        id="claude-sonnet-4-6",
        provider=LLMProvider.ANTHROPIC,
        context_window=200_000,
        prefers_xml_tags=True,
        supports_thinking=True,
        supports_prompt_caching=True,
    ),
    "claude-haiku-4-5-20251001": ModelCard(
        id="claude-haiku-4-5-20251001",
        provider=LLMProvider.ANTHROPIC,
        context_window=200_000,
        prefers_xml_tags=True,
        supports_prompt_caching=True,
    ),
    "gpt-4o": ModelCard(
        id="gpt-4o",
        provider=LLMProvider.OPENAI,
        context_window=128_000,
        supports_native_json=True,
    ),
    "gpt-4o-mini": ModelCard(
        id="gpt-4o-mini",
        provider=LLMProvider.OPENAI,
        context_window=128_000,
        supports_native_json=True,
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
