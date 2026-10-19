"""Tests for configuration settings and secret protection."""

import pytest
from pydantic import SecretStr, ValidationError

from campaign.config import Settings


def test_config_defaults():
    s = Settings(_env_file=None)
    assert s.llm_mode == "scripted"
    assert s.search_backend == "fixture"
    assert s.max_tool_calls == 15
    assert s.cost_ceiling_usd == 0.25
    assert s.gemini_model == "gemini-3.8-flash"
    assert s.gemini_api_key.get_secret_value() == ""


def test_config_never_echoes_secret():
    s = Settings(GEMINI_API_KEY=SecretStr("super-secret-key-12345"))
    # __str__ and __repr__ must not contain the plaintext secret
    assert "super-secret-key-12345" not in str(s)
    assert "super-secret-key-12345" not in repr(s)
    assert "super-secret-key-12345" not in str(s.gemini_api_key)
    assert "super-secret-key-12345" not in repr(s.gemini_api_key)
    assert "super-secret-key-12345" not in str(s.model_dump())


def test_config_gemini_mode_requires_key():
    # If mode is gemini and key is empty, must fail
    with pytest.raises(ValidationError, match="GEMINI_API_KEY must be provided"):
        Settings(LLM_MODE="gemini", GEMINI_API_KEY=SecretStr(""))

    # If key is provided, should succeed
    s = Settings(LLM_MODE="gemini", GEMINI_API_KEY=SecretStr("valid-key"))
    assert s.llm_mode == "gemini"
    assert s.gemini_api_key.get_secret_value() == "valid-key"
