"""Tests for model capability flags and prompt assembly."""

from skellington.core.models import MODELS, ModelCard, get_model_card
from skellington.core.types import LLMProvider
from skellington.prompts import assemble_prompt


def test_get_model_card_known_returns_registered_card():
    card = get_model_card("claude-opus-4-7")
    assert card.id == "claude-opus-4-7"
    assert card.prefers_xml_tags is True
    assert card is MODELS["claude-opus-4-7"]


def test_get_model_card_unknown_returns_conservative_fallback():
    card = get_model_card("some-future-model-99")
    assert card.id == "some-future-model-99"
    assert card.max_parallel_tools == 1
    assert card.supports_native_json is False


def test_assemble_appends_json_fragment_when_no_native_json():
    card = ModelCard(id="x", provider=LLMProvider.ANTHROPIC, context_window=8000)
    out = assemble_prompt("You are a helper.", card)
    assert out.startswith("You are a helper.")
    assert "JSON" in out


def test_assemble_omits_json_fragment_when_native_json_supported():
    card = ModelCard(
        id="x",
        provider=LLMProvider.OPENAI,
        context_window=8000,
        supports_native_json=True,
    )
    out = assemble_prompt("You are a helper.", card)
    assert "JSON" not in out


def test_assemble_appends_xml_fragment_when_preferred():
    card = ModelCard(
        id="x",
        provider=LLMProvider.ANTHROPIC,
        context_window=8000,
        supports_native_json=True,  # suppress JSON fragment to isolate XML
        prefers_xml_tags=True,
    )
    out = assemble_prompt("base", card)
    assert "<reasoning>" in out


def test_assemble_appends_serial_tools_fragment_when_no_parallelism():
    card = ModelCard(
        id="x",
        provider=LLMProvider.ANTHROPIC,
        context_window=8000,
        supports_native_json=True,
        max_parallel_tools=1,
    )
    out = assemble_prompt("base", card)
    assert "one at a time" in out


def test_assemble_preserves_base_when_no_flags_trigger():
    card = ModelCard(
        id="x",
        provider=LLMProvider.OPENAI,
        context_window=8000,
        supports_native_json=True,
    )
    out = assemble_prompt("just the base.", card)
    assert out == "just the base."
