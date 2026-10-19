"""Configuration settings for the marketing campaign agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    llm_mode: Literal["scripted", "gemini"] = Field(default="scripted", alias="LLM_MODE")
    gemini_api_key: SecretStr = Field(default=SecretStr(""), alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")

    # Search Backend
    search_backend: Literal["fixture", "ddgs"] = Field(default="fixture", alias="SEARCH_BACKEND")

    # Limits and Bounds
    max_tool_calls: int = Field(default=15, ge=1, le=100, alias="MAX_TOOL_CALLS")
    max_model_calls: int = Field(default=20, ge=1, le=100, alias="MAX_MODEL_CALLS")
    cost_ceiling_usd: float = Field(default=0.25, ge=0.01, le=10.0, alias="COST_CEILING_USD")
    price_input_per_m: float = Field(default=1.50, ge=0.0, alias="PRICE_INPUT_PER_M")
    price_output_per_m: float = Field(default=7.50, ge=0.0, alias="PRICE_OUTPUT_PER_M")
    max_output_tokens: int = Field(default=2048, ge=256, le=8192, alias="MAX_OUTPUT_TOKENS")

    # Rate Limiting
    rate_limit_runs: int = Field(default=5, ge=1, alias="RATE_LIMIT_RUNS")
    rate_limit_window_s: int = Field(default=3600, ge=1, alias="RATE_LIMIT_WINDOW_S")

    # Data & Log Paths
    customers_db: Path = Field(default=Path("data/customers.db"), alias="CUSTOMERS_DB")
    runs_db: Path = Field(default=Path("data/runs.db"), alias="RUNS_DB")
    sql_audit_path: Path = Field(default=Path("audit/sql_audit.jsonl"), alias="SQL_AUDIT_PATH")
    trace_log_path: Path = Field(default=Path("logs/agent_trace.jsonl"), alias="TRACE_LOG_PATH")

    # Logging & Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: SecretStr = Field(default=SecretStr(""), alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="campaign-agent", alias="LANGSMITH_PROJECT")

    @model_validator(mode="after")
    def validate_gemini_key_if_gemini_mode(self) -> Settings:
        if self.llm_mode == "gemini" and not self.gemini_api_key.get_secret_value().strip():
            raise ValueError("GEMINI_API_KEY must be provided when LLM_MODE is 'gemini'")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
