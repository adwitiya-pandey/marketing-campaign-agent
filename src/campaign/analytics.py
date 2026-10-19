"""Deterministic mock reach analytics."""

from __future__ import annotations

from typing import Any

from campaign.models import ChannelType, SegmentType

# Documented baseline reach per audience segment
BASE_REACH: dict[SegmentType, int] = {
    "fitness-enthusiasts": 50_000,
    "young-professionals": 45_000,
    "eco-conscious-families": 35_000,
    "students": 40_000,
}

# Documented channel multiplier rates
CHANNEL_RATES: dict[ChannelType, float] = {
    "instagram": 1.2,
    "google_ads": 1.0,
    "email": 0.8,
}


def estimate_reach(
    segment: SegmentType,
    channel: ChannelType,
    budget_usd: float,
) -> dict[str, Any]:
    """Estimate mock campaign reach based on segment, channel, and budget."""
    if budget_usd < 50.0 or budget_usd > 100_000.0:
        raise ValueError(f"budget_usd must be between 50.0 and 100,000.0, got {budget_usd}")

    base = BASE_REACH[segment]
    rate = CHANNEL_RATES[channel]
    budget_factor = min(1.0, budget_usd / 5000.0) ** 0.5
    reach = round(base * rate * budget_factor)

    return {
        "estimated_reach": reach,
        "assumptions": "mock",
    }
