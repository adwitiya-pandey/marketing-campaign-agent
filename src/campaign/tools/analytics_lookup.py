"""Analytics reach estimation tool."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from campaign.analytics import estimate_reach
from campaign.models import AnalyticsLookupArgs, ChannelType, SegmentType


@tool(args_schema=AnalyticsLookupArgs)
def analytics_lookup(
    segment: SegmentType,
    channel: ChannelType,
    budget_usd: float,
) -> str:
    """Look up deterministic estimated audience reach for a segment, channel, and budget."""
    try:
        res = estimate_reach(segment=segment, channel=channel, budget_usd=budget_usd)
        return json.dumps(res, ensure_ascii=True)
    except (ValueError, TypeError) as e:
        return json.dumps({"error": f"ANALYTICS_ERROR: {e}"}, ensure_ascii=True)


def _handle_error(e: Exception) -> str:
    return json.dumps({"error": f"INVALID_ARG: {e}"}, ensure_ascii=True)


analytics_lookup.handle_validation_error = _handle_error
analytics_lookup.handle_tool_error = _handle_error
