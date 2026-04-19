"""
Configuration management for Skellington.

Learning goal: Pydantic Settings for type-safe, environment-driven config.
Settings are loaded from environment variables and .env files.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from skellington.core.types import LLMProvider


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables.

    Pydantic Settings automatically reads from:
    1. Environment variables
    2. .env file (if present)
    3. Defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,  # Allow field name OR alias in constructor (needed for tests)
    )

    # ------------------------------------------------------------------
    # LLM Providers
    # ------------------------------------------------------------------
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")

    default_llm_provider: LLMProvider = Field(
        default=LLMProvider.ANTHROPIC, alias="DEFAULT_LLM_PROVIDER"
    )
    default_llm_model: str = Field(default="claude-opus-4-5", alias="DEFAULT_LLM_MODEL")
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")

    # Per-agent model overrides
    jack_model: str | None = Field(default=None, alias="JACK_MODEL")
    sally_model: str | None = Field(default=None, alias="SALLY_MODEL")
    oogie_model: str | None = Field(default=None, alias="OOGIE_MODEL")
    zero_model: str | None = Field(default=None, alias="ZERO_MODEL")
    validators_model: str | None = Field(default=None, alias="VALIDATORS_MODEL")
    mayor_model: str | None = Field(default=None, alias="MAYOR_MODEL")

    # ------------------------------------------------------------------
    # Web Search
    # ------------------------------------------------------------------
    brave_search_api_key: str | None = Field(default=None, alias="BRAVE_SEARCH_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    search_results_limit: int = Field(default=10, alias="SEARCH_RESULTS_LIMIT")

    # ------------------------------------------------------------------
    # Local Models
    # ------------------------------------------------------------------
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_default_model: str = Field(default="llama3.2", alias="OLLAMA_DEFAULT_MODEL")

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    memory_db_path: Path = Field(
        default=Path("./data/skellington_memory.db"), alias="MEMORY_DB_PATH"
    )

    # ------------------------------------------------------------------
    # Web UI
    # ------------------------------------------------------------------
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=8000, alias="WEB_PORT")
    web_reload: bool = Field(default=True, alias="WEB_RELOAD")

    # ------------------------------------------------------------------
    # MCP Servers
    # ------------------------------------------------------------------
    code_exec_timeout: int = Field(default=30, alias="CODE_EXEC_TIMEOUT")
    # NoDecode stops pydantic-settings from trying to JSON-parse the env value
    # before our validator runs, so we can accept a comma-delimited string.
    filesystem_allowed_paths: Annotated[list[str], NoDecode] = Field(
        default=["./", "~/projects"], alias="FILESYSTEM_ALLOWED_PATHS"
    )

    @field_validator("filesystem_allowed_paths", mode="before")
    @classmethod
    def _parse_allowed_paths(cls, v: object) -> object:
        """Accept either a JSON array (['a','b']) or a comma-delimited string (a,b)."""
        if not isinstance(v, str):
            return v
        s = v.strip()
        if s.startswith("["):
            return json.loads(s)
        return [p.strip() for p in s.split(",") if p.strip()]

    def get_model_for_agent(self, agent_name: str) -> str:
        """Return the configured model for a specific agent, falling back to default."""
        override = getattr(self, f"{agent_name}_model", None)
        return override or self.default_llm_model

    def has_provider(self, provider: LLMProvider) -> bool:
        """Check if a given LLM provider has an API key configured."""
        key_map = {
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.GOOGLE: self.google_api_key,
        }
        return bool(key_map.get(provider))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached so the .env file is only parsed once. To reload (e.g. in tests),
    call get_settings.cache_clear() first.
    """
    return Settings()
