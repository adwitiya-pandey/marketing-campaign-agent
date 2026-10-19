"""Tests for LangSmith tracing configuration, validation, and invoke metadata helpers."""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from campaign.config import Settings
from campaign.tracing import get_invoke_config, validate_tracing_settings


def test_tracing_disabled_by_default() -> None:
    """Verify tracing is disabled by default and sets environment variable."""
    settings = Settings(langsmith_tracing=False)
    enabled = validate_tracing_settings(settings)
    assert not enabled
    assert os.environ.get("LANGSMITH_TRACING") == "false"


def test_tracing_enabled_with_valid_key() -> None:
    """Verify tracing enables when valid API key and project are provided."""
    settings = Settings(
        langsmith_tracing=True,
        langsmith_api_key=SecretStr("lsv2_pt_testkey_12345"),
        langsmith_project="test-project",
    )
    enabled = validate_tracing_settings(settings)
    assert enabled
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_API_KEY") == "lsv2_pt_testkey_12345"
    assert os.environ.get("LANGSMITH_PROJECT") == "test-project"

    # Reset back to false for safety
    os.environ["LANGSMITH_TRACING"] = "false"


def test_tracing_raises_when_key_missing() -> None:
    """Verify ValueError is raised if tracing is enabled but key is empty."""
    settings = Settings(langsmith_tracing=True, langsmith_api_key=SecretStr(""))
    with pytest.raises(
        ValueError, match="LANGSMITH_TRACING is true but LANGSMITH_API_KEY is missing"
    ):
        validate_tracing_settings(settings)


def test_get_invoke_config_standard_fields() -> None:
    """Verify invoke config produces correct tags, metadata, and run_name."""
    cfg = get_invoke_config(run_id="RUN-20261019-1234", phase="research")
    assert cfg["run_name"] == "campaign-agent-research"
    assert cfg["tags"] == ["campaign-agent", "research"]
    assert cfg["metadata"] == {"run_id": "RUN-20261019-1234", "phase": "research"}


def test_get_invoke_config_custom_fields() -> None:
    """Verify invoke config allows custom run_name, extra_tags, and extra_metadata."""
    cfg = get_invoke_config(
        run_id="RUN-20261019-9999",
        phase="drafting",
        run_name="custom-phase2-draft",
        extra_tags=["high-priority", "experiment-b"],
        extra_metadata={"channel": "instagram", "retry_count": 1},
    )
    assert cfg["run_name"] == "custom-phase2-draft"
    assert cfg["tags"] == ["campaign-agent", "drafting", "high-priority", "experiment-b"]
    assert cfg["metadata"]["run_id"] == "RUN-20261019-9999"
    assert cfg["metadata"]["phase"] == "drafting"
    assert cfg["metadata"]["channel"] == "instagram"
    assert cfg["metadata"]["retry_count"] == 1
