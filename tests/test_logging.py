"""Tests for structured logging and sensitive data protection."""

import json

from campaign.logging_setup import (
    configure_logging,
    current_phase,
    current_run_id,
    get_logger,
)


def test_logging_allowed_fields_and_contextvars(capsys):
    configure_logging(log_level="INFO")
    current_run_id.set("RUN-20261019-0001")
    current_phase.set("research")

    logger = get_logger("test_logger")
    logger.info(
        "tool_executed",
        tool="web_search",
        tool_calls_requested=3,
        duration_ms=12.5,
        ok=True,
    )

    captured = capsys.readouterr().out.strip()
    data = json.loads(captured)

    assert data["event"] == "tool_executed"
    assert data["run_id"] == "RUN-20261019-0001"
    assert data["phase"] == "research"
    assert data["tool"] == "web_search"
    assert data["ok"] is True
    assert data["duration_ms"] == 12.5


def test_logging_sensitive_data_stripped(capsys):
    configure_logging(log_level="INFO")
    logger = get_logger("test_sanitizer")

    # Attempt to log sensitive fields: product text, secret keys, sql row data
    secret_key = "AIzaSyDummySecretKey1234567890"
    product_desc = "Top secret patent-pending water bottle with advanced cooling"
    raw_customer_row = {"name": "John Doe", "email": "john@example.com"}

    logger.info(
        "test_event",
        api_key=secret_key,
        product_description=product_desc,
        customer_row=raw_customer_row,
        row_count=42,  # allowed
    )

    captured = capsys.readouterr().out.strip()
    assert secret_key not in captured
    assert product_desc not in captured
    assert "john@example.com" not in captured
    assert "John Doe" not in captured

    data = json.loads(captured)
    assert "api_key" not in data
    assert "product_description" not in data
    assert "customer_row" not in data
    assert data["row_count"] == 42
