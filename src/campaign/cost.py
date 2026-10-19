"""Notional token cost tracking and budget ceiling enforcement."""

from __future__ import annotations


class BudgetExceeded(Exception):
    """Raised when notional LLM token usage crosses the configured cost ceiling."""


class CostTracker:
    """Tracks cumulative token usage and notional cost against a configured ceiling."""

    def __init__(
        self,
        prior_usd: float = 0.0,
        ceiling_usd: float = 0.25,
        price_in: float = 1.50,
        price_out: float = 7.50,
    ) -> None:
        self.prior_usd = prior_usd
        self.ceiling_usd = ceiling_usd
        self.price_in = price_in
        self.price_out = price_out

        self.total_cost_usd = prior_usd
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def add_tokens(self, input_tokens: int | None, output_tokens: int | None) -> float:
        """Add tokens from a model invocation step and update total notional cost."""
        in_tok = input_tokens if input_tokens is not None else 0
        out_tok = output_tokens if output_tokens is not None else 0

        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok

        # Cost formula: tokens * (price_per_m / 1,000,000)
        step_cost = (in_tok * (self.price_in / 1_000_000.0)) + (
            out_tok * (self.price_out / 1_000_000.0)
        )
        self.total_cost_usd += step_cost
        return self.total_cost_usd

    def is_exceeded(self) -> bool:
        """Return True if total notional cost strictly exceeds the ceiling."""
        return self.total_cost_usd > self.ceiling_usd
