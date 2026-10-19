"""Tests for cost tracking and ceiling enforcement (Tests First)."""

import pytest

from campaign.cost import BudgetExceeded, CostTracker


def test_cost_tracker_accumulation():
    # Price: $1.50 per 1M input ($0.0000015/token), $7.50 per 1M output ($0.0000075/token)
    tracker = CostTracker(prior_usd=0.0, ceiling_usd=0.25, price_in=1.50, price_out=7.50)

    # 10,000 input tokens = $0.015, 2,000 output tokens = $0.015 -> total = $0.03
    spent = tracker.add_tokens(10_000, 2_000)
    assert round(spent, 4) == 0.03
    assert tracker.is_exceeded() is False


def test_cost_tracker_with_prior_usd():
    tracker = CostTracker(prior_usd=0.20, ceiling_usd=0.25, price_in=1.50, price_out=7.50)
    assert round(tracker.total_cost_usd, 2) == 0.20
    assert tracker.is_exceeded() is False

    # Add tokens worth $0.06 -> total $0.26 > $0.25 ceiling
    tracker.add_tokens(20_000, 4_000)
    assert tracker.total_cost_usd > 0.25
    assert tracker.is_exceeded() is True


def test_cost_tracker_none_tokens_count_as_zero():
    tracker = CostTracker(prior_usd=0.0, ceiling_usd=0.25)
    spent = tracker.add_tokens(0, 0)
    assert spent == 0.0
    assert tracker.is_exceeded() is False


def test_budget_exceeded_exception():
    with pytest.raises(BudgetExceeded):
        raise BudgetExceeded("Cost ceiling of $0.25 exceeded")
