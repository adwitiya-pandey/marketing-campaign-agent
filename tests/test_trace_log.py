"""Tests for append-only trace logging."""

import json

from campaign.trace_log import TraceLogger, sha256_digest


def test_sha256_helper():
    text = "hello world"
    digest = sha256_digest(text)
    assert len(digest) == 64
    assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_trace_log_model_step(tmp_path):
    log_file = tmp_path / "trace.jsonl"
    logger = TraceLogger(trace_file=log_file)

    rec = logger.log_model_step(
        run_id="RUN-20261019-0001",
        step=1,
        tool_calls_requested=3,
        input_tokens=150,
        output_tokens=40,
        running_cost_usd=0.0012,
        content='{"thought": "researching competitors"}',
    )

    assert rec["run_id"] == "RUN-20261019-0001"
    assert rec["step"] == 1
    assert rec["tool_calls_requested"] == 3
    assert rec["input_tokens"] == 150
    assert rec["output_tokens"] == 40
    assert rec["running_cost_usd"] == 0.0012
    assert "content_sha256" in rec

    # Verify file content
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["type"] == "model_step"
    assert parsed["content_sha256"] == rec["content_sha256"]


def test_trace_log_tool_call_truncation(tmp_path):
    log_file = tmp_path / "trace.jsonl"
    logger = TraceLogger(trace_file=log_file)

    long_args = "x" * 500
    rec = logger.log_tool_call(
        run_id="RUN-20261019-0001",
        step=2,
        tool="sql_query",
        args_str=long_args,
        ok=True,
        result_bytes=1024,
        duration_ms=45.2,
    )

    assert rec["tool"] == "sql_query"
    assert len(rec["args"]) == 300
    assert rec["ok"] is True
    assert rec["result_bytes"] == 1024
    assert rec["duration_ms"] == 45.2

    # Second entry in same file
    logger.log_tool_call(
        run_id="RUN-20261019-0001",
        step=3,
        tool="analytics_lookup",
        args_str='{"segment": "students"}',
        ok=False,
        error_code="INVALID_ARG",
        duration_ms=5.0,
    )

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed_err = json.loads(lines[1])
    assert parsed_err["ok"] is False
    assert parsed_err["error_code"] == "INVALID_ARG"
