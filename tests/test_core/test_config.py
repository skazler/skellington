"""Tests for configuration management."""

import pytest

from skellington.core.config import Settings, get_settings
from skellington.core.types import LLMProvider


def test_settings_defaults():
    s = Settings()
    assert s.default_llm_provider == LLMProvider.ANTHROPIC
    assert s.max_tokens == 4096
    assert s.web_port == 8000


def test_get_model_for_agent_default():
    s = Settings(default_llm_model="claude-opus-4-5")
    model = s.get_model_for_agent("jack")
    assert model == "claude-opus-4-5"


def test_get_model_for_agent_override():
    s = Settings(default_llm_model="gpt-4o", jack_model="claude-opus-4-5")
    assert s.get_model_for_agent("jack") == "claude-opus-4-5"
    assert s.get_model_for_agent("sally") == "gpt-4o"


def test_has_provider_false():
    s = Settings()
    # No API keys set in test environment
    assert s.has_provider(LLMProvider.ANTHROPIC) is False
