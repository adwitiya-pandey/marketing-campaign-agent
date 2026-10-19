"""Agent middleware for cost ceiling enforcement, bounds, and trace logging."""

from __future__ import annotations

import json
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

from campaign.cost import BudgetExceeded, CostTracker
from campaign.trace_log import TraceLogger


class CostCeilingMiddleware(AgentMiddleware):
    """Enforces per-run notional cost ceiling after each model invocation."""

    def __init__(self, cost_tracker: CostTracker) -> None:
        super().__init__()
        self.cost_tracker = cost_tracker

    def after_model(self, state: dict[str, Any], runtime: Any) -> None:
        messages = state.get("messages", [])
        if not messages:
            return

        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            usage = last_msg.usage_metadata or {}
            in_tok = usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            self.cost_tracker.add_tokens(in_tok, out_tok)

            if self.cost_tracker.is_exceeded():
                raise BudgetExceeded(
                    f"Cost ceiling exceeded: ${self.cost_tracker.total_cost_usd:.4f} > "
                    f"${self.cost_tracker.ceiling_usd:.4f}"
                )
        return


class TraceMiddleware(AgentMiddleware):
    """Logs model steps and tool calls to structured append-only trace log."""

    def __init__(
        self,
        trace_logger: TraceLogger,
        run_id: str,
        cost_tracker: CostTracker,
    ) -> None:
        super().__init__()
        self.trace_logger = trace_logger
        self.run_id = run_id
        self.cost_tracker = cost_tracker
        self.step_counter = 0

    def after_model(self, state: dict[str, Any], runtime: Any) -> None:
        self.step_counter += 1
        messages = state.get("messages", [])
        if not messages:
            return

        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage):
            tool_calls_req = (
                len(last_msg.tool_calls)
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls
                else 0
            )
            usage = last_msg.usage_metadata or {}
            in_tok = usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            content_str = (
                last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)
            )

            self.trace_logger.log_model_step(
                run_id=self.run_id,
                step=self.step_counter,
                tool_calls_requested=tool_calls_req,
                input_tokens=in_tok,
                output_tokens=out_tok,
                running_cost_usd=self.cost_tracker.total_cost_usd,
                content=content_str,
            )
        return

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        t0 = time.perf_counter()
        tool_call = getattr(request, "tool_call", {}) or {}
        tool_name = tool_call.get("name", "unknown_tool")
        args_data = tool_call.get("args", {})
        args_str = json.dumps(args_data, ensure_ascii=True, separators=(",", ":"))

        error_code: str | None = None
        ok = True
        try:
            res = handler(request)
            duration_ms = (time.perf_counter() - t0) * 1000
            content = getattr(res, "content", "")
            content_str = content if isinstance(content, str) else str(content)
            result_bytes = len(content_str.encode("utf-8"))

            if getattr(res, "status", "") == "error" or '"error":' in content_str:
                ok = False
                error_code = "TOOL_ERROR"

            self.trace_logger.log_tool_call(
                run_id=self.run_id,
                step=self.step_counter,
                tool=tool_name,
                args_str=args_str,
                ok=ok,
                error_code=error_code,
                result_bytes=result_bytes,
                duration_ms=duration_ms,
            )
            return res
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            self.trace_logger.log_tool_call(
                run_id=self.run_id,
                step=self.step_counter,
                tool=tool_name,
                args_str=args_str,
                ok=False,
                error_code=type(e).__name__,
                result_bytes=0,
                duration_ms=duration_ms,
            )
            raise
