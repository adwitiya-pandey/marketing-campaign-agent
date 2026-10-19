"""Append-only trace logging for model steps and tool calls."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def sha256_digest(text: str) -> str:
    """Compute hex SHA256 digest of input string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TraceLogger:
    """Thread-safe append-only writer for agent trace events in JSONL format."""

    def __init__(self, trace_file: Path | str = "logs/agent_trace.jsonl") -> None:
        self.trace_file = Path(trace_file)

    def _append_line(self, data: dict[str, Any]) -> None:
        line = json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n"
        with _LOCK:
            self.trace_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(line)

    def log_model_step(
        self,
        *,
        run_id: str,
        step: int,
        tool_calls_requested: int,
        input_tokens: int,
        output_tokens: int,
        running_cost_usd: float,
        content: str = "",
    ) -> dict[str, Any]:
        """Record a model invocation step with token metrics and content digest."""
        record: dict[str, Any] = {
            "type": "model_step",
            "ts": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "step": step,
            "tool_calls_requested": tool_calls_requested,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "running_cost_usd": round(running_cost_usd, 6),
            "content_sha256": sha256_digest(content),
        }
        self._append_line(record)
        return record

    def log_tool_call(
        self,
        *,
        run_id: str,
        step: int,
        tool: str,
        args_str: str,
        ok: bool,
        error_code: str | None = None,
        result_bytes: int = 0,
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Record an executed tool call with truncated args and timing."""
        truncated_args = args_str[:300] if len(args_str) > 300 else args_str
        record: dict[str, Any] = {
            "type": "tool_call",
            "ts": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "step": step,
            "tool": tool,
            "args": truncated_args,
            "ok": ok,
            "error_code": error_code,
            "result_bytes": result_bytes,
            "duration_ms": round(duration_ms, 2),
        }
        self._append_line(record)
        return record
