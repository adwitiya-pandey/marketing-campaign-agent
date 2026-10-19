"""Structured logging configuration using structlog."""

from __future__ import annotations

import contextvars
import logging
import sys
from pathlib import Path
from typing import Any

import structlog

# Context variables for request/run tracing
current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_run_id", default=None
)
current_phase: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_phase", default=None
)

# Explicitly allowed fields in log output to satisfy SPEC 12 & S9 security requirements
ALLOWED_LOG_FIELDS = {
    "event",
    "level",
    "timestamp",
    "logger",
    "run_id",
    "phase",
    "user_id",
    "tool_name",
    "tool",
    "status",
    "status_code",
    "code",
    "count",
    "row_count",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "running_cost_usd",
    "ok",
    "truncated",
    "accepted",
    "content_sha256",
    "step",
    "tool_calls_requested",
    "tool_calls_used",
    "exception",
}

DISALLOWED_PATTERNS = [
    "key",
    "secret",
    "token",
    "password",
    "description",
    "brief",
    "product",
    "row",
    "customer",
    "email",
]


def add_contextvars(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject active contextvars into the event dictionary."""
    run_id = current_run_id.get()
    if run_id:
        event_dict["run_id"] = run_id
    phase = current_phase.get()
    if phase:
        event_dict["phase"] = phase
    return event_dict


def filter_allowed_fields(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Ensure no product text, secret keys, or raw SQL rows leak into structured logs."""
    sanitized: dict[str, Any] = {}
    for k, v in event_dict.items():
        k_lower = k.lower()
        # Explicit allowlist check
        if k in ALLOWED_LOG_FIELDS:
            # Further protect against sensitive values in strings
            if isinstance(v, str) and ("AIza" in v or "sk-" in v):
                sanitized[k] = "[REDACTED_KEY]"
                continue
            sanitized[k] = v
        elif any(pattern in k_lower for pattern in DISALLOWED_PATTERNS):
            # Omit disallowed fields entirely
            continue
    return sanitized


def configure_logging(log_level: str = "INFO", log_file: Path | str | None = None) -> None:
    """Configure structlog processors and handlers for JSON output."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        filter_allowed_fields,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
        root_logger.addHandler(file_handler)


def get_logger(name: str = "campaign") -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)
