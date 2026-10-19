"""Tests for mock analytics reach estimation (Tests First)."""

import pytest
from pydantic import ValidationError

from campaign.analytics import estimate_reach

# Hand-computed reach for 6 distinct inputs
HAND_COMPUTED_CASES = [
    ("fitness-enthusiasts", "instagram", 5000.0, 60000),
    ("young-professionals", "google_ads", 5000.0, 45000),
    ("eco-conscious-families", "email", 5000.0, 28000),
    ("students", "instagram", 1250.0, 24000),
    ("fitness-enthusiasts", "google_ads", 1250.0, 25000),
    ("students", "email", 10000.0, 32000),
]


@pytest.mark.parametrize("segment,channel,budget,expected_reach", HAND_COMPUTED_CASES)
def test_hand_computed_reach(segment, channel, budget, expected_reach):
    res = estimate_reach(segment=segment, channel=channel, budget_usd=budget)
    assert res["estimated_reach"] == expected_reach
    assert res["assumptions"] == "mock"


def test_reach_monotonic_in_budget():
    """Reach must increase or remain constant as budget increases."""
    segment = "young-professionals"
    channel = "instagram"
    budgets = [100.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0]

    reaches = [
        estimate_reach(segment=segment, channel=channel, budget_usd=b)["estimated_reach"]
        for b in budgets
    ]

    for i in range(len(reaches) - 1):
        assert reaches[i] <= reaches[i + 1]


def test_analytics_bounds():
    # Budget below min (50.0)
    with pytest.raises((ValueError, ValidationError)):
        estimate_reach(segment="students", channel="instagram", budget_usd=40.0)

    # Budget above max (100,000.0)
    with pytest.raises((ValueError, ValidationError)):
        estimate_reach(segment="students", channel="instagram", budget_usd=150000.0)
