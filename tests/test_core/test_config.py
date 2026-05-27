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


def test_has_provider_false(monkeypatch):
    # Isolate from any ambient .env or exported API keys so we can assert on
    # the "no key configured" branch.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.has_provider(LLMProvider.ANTHROPIC) is False


def test_get_settings_warns_on_unknown_model(monkeypatch, capsys):
    from skellington.core import config as config_module

    monkeypatch.setenv("DEFAULT_LLM_MODEL", "totally-made-up-model-99")
    config_module.get_settings.cache_clear()
    try:
        config_module.get_settings()
        out = capsys.readouterr().out
        assert "totally-made-up-model-99" in out
        assert "not in registry" in out
    finally:
        config_module.get_settings.cache_clear()


def test_get_settings_silent_on_known_model(monkeypatch, capsys):
    from skellington.core import config as config_module

    monkeypatch.setenv("DEFAULT_LLM_MODEL", "claude-opus-4-7")
    config_module.get_settings.cache_clear()
    try:
        config_module.get_settings()
        out = capsys.readouterr().out
        assert "not in registry" not in out
    finally:
        config_module.get_settings.cache_clear()
