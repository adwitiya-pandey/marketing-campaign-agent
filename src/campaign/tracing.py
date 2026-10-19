"""LangSmith tracing configuration, validation, and invoke metadata helpers."""

from __future__ import annotations

import os
from typing import Any

from campaign.config import Settings, get_settings
from campaign.logging_setup import get_logger

logger = get_logger("campaign.tracing")


def validate_tracing_settings(settings: Settings | None = None) -> bool:
    """Validate LangSmith configuration settings and configure environment accordingly.

    Returns:
        bool: True if tracing is enabled and configured, False otherwise.

    Raises:
        ValueError: If LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is missing or empty.
    """
    cfg = settings if settings is not None else get_settings()

    if not cfg.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.info("langsmith_tracing_disabled")
        return False

    api_key = cfg.langsmith_api_key.get_secret_value().strip()
    if not api_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        raise ValueError("LANGSMITH_TRACING is true but LANGSMITH_API_KEY is missing or empty")

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = cfg.langsmith_project
    logger.info("langsmith_tracing_enabled", project=cfg.langsmith_project)
    return True


def get_invoke_config(
    *,
    run_id: str,
    phase: str,
    run_name: str | None = None,
    extra_tags: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct standard LangChain RunnableConfig dictionary for agent invocations."""
    tags = ["campaign-agent", phase]
    if extra_tags:
        tags.extend(extra_tags)

    metadata: dict[str, Any] = {
        "run_id": run_id,
        "phase": phase,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "run_name": run_name or f"campaign-agent-{phase}",
        "tags": tags,
        "metadata": metadata,
    }
