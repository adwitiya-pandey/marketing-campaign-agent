"""LangChain agent construction and execution for Phase 1 and Phase 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from campaign.config import get_settings
from campaign.cost import BudgetExceeded, CostTracker
from campaign.middleware import CostCeilingMiddleware, TraceMiddleware
from campaign.models import (
    CampaignAngle,
    CampaignAngles,
    CampaignPackage,
    ProductBrief,
    RunStatus,
)
from campaign.prompts import PHASE1_SYSTEM_PROMPT, PHASE2_SYSTEM_PROMPT, REPAIR_PROMPT
from campaign.tools import analytics_lookup, draft_copy, sql_query, web_search
from campaign.trace_log import TraceLogger
from campaign.tracing import get_invoke_config


@dataclass
class Phase1Result:
    """Outcome of Phase 1 campaign research and angle proposal."""

    status: RunStatus
    angles: CampaignAngles | None
    tool_calls_used: int
    cost_usd: float
    raw_output: str = ""


@dataclass
class Phase2Result:
    """Outcome of Phase 2 advertising copy drafting for an approved angle."""

    status: RunStatus
    package: CampaignPackage | None
    tool_calls_used: int
    cost_usd: float
    raw_output: str = ""


def extract_json_str(text: str) -> str:
    """Strip markdown code fence blocks if present."""
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
            return "\n".join(lines[1:]).strip()
    return s


def build_agent(
    model: Any,
    tools: list[Any],
    system_prompt: str,
    middleware: list[Any],
) -> Any:
    """Wrap langchain.agents.create_agent with middleware and system prompt."""
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
    )


def count_executed_tool_calls(messages: list[Any]) -> int:
    """Count executed tool calls, excluding the terminal ToolCallLimit blocker."""
    return sum(
        1
        for m in messages
        if getattr(m, "type", "") == "tool"
        and "Tool call limit" not in str(getattr(m, "content", ""))
    )


def was_tool_limit_hit(messages: list[Any]) -> bool:
    """Return True if any tool message signals that tool limit was reached."""
    return any(
        getattr(m, "type", "") == "tool" and "Tool call limit" in str(getattr(m, "content", ""))
        for m in messages
    ) or (bool(messages) and "Tool call limit" in str(getattr(messages[-1], "content", "")))


def run_phase1(
    brief: ProductBrief,
    model: Any,
    run_id: str,
    max_tool_calls: int | None = None,
    cost_ceiling_usd: float | None = None,
    trace_file: Path | str | None = None,
) -> Phase1Result:
    """Execute Phase 1 research returning 5 distinct CampaignAngles."""
    settings = get_settings()
    tool_limit = max_tool_calls if max_tool_calls is not None else settings.max_tool_calls
    ceiling_usd = cost_ceiling_usd if cost_ceiling_usd is not None else settings.cost_ceiling_usd
    trace_path = trace_file if trace_file is not None else settings.trace_log_path

    if tool_limit <= 0:
        return Phase1Result(status="LIMIT_REACHED", angles=None, tool_calls_used=0, cost_usd=0.0)
    if ceiling_usd <= 0:
        return Phase1Result(status="BUDGET_EXCEEDED", angles=None, tool_calls_used=0, cost_usd=0.0)

    cost_tracker = CostTracker(prior_usd=0.0, ceiling_usd=ceiling_usd)
    trace_logger = TraceLogger(trace_file=trace_path)

    middleware = [
        ToolCallLimitMiddleware(run_limit=tool_limit, exit_behavior="end"),
        ModelCallLimitMiddleware(run_limit=settings.max_model_calls, exit_behavior="end"),
        CostCeilingMiddleware(cost_tracker=cost_tracker),
        TraceMiddleware(trace_logger=trace_logger, run_id=run_id, cost_tracker=cost_tracker),
    ]

    tools = [web_search, sql_query, analytics_lookup]
    agent = build_agent(
        model=model,
        tools=tools,
        system_prompt=PHASE1_SYSTEM_PROMPT,
        middleware=middleware,
    )

    prompt = (
        "Please research and propose exactly 5 campaign angles for the following product and audience segment:\n"
        f"<product>\nName: {brief.name}\nDescription: {brief.description}\n"
        f"Target Segment: {brief.segment}\nBudget USD: {brief.budget_usd}\n</product>"
    )

    invoke_config = get_invoke_config(
        run_id=run_id, phase="research", run_name="campaign-phase1-research"
    )
    invoke_config["recursion_limit"] = 30

    try:
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]}, config=invoke_config)
    except BudgetExceeded:
        return Phase1Result(
            status="BUDGET_EXCEEDED",
            angles=None,
            tool_calls_used=0,
            cost_usd=cost_tracker.total_cost_usd,
        )

    messages = response.get("messages", [])
    executed_tools = count_executed_tool_calls(messages)
    limit_hit = was_tool_limit_hit(messages)

    if limit_hit:
        return Phase1Result(
            status="LIMIT_REACHED",
            angles=None,
            tool_calls_used=executed_tools,
            cost_usd=cost_tracker.total_cost_usd,
        )

    last_msg = messages[-1] if messages else None
    raw_content = getattr(last_msg, "content", "") if last_msg else ""
    cleaned_json = extract_json_str(raw_content)

    # Validate output against CampaignAngles schema
    try:
        angles = CampaignAngles.model_validate_json(cleaned_json)
        return Phase1Result(
            status="AWAITING_APPROVAL",
            angles=angles,
            tool_calls_used=executed_tools,
            cost_usd=cost_tracker.total_cost_usd,
            raw_output=raw_content,
        )
    except (ValidationError, ValueError) as err:
        # Repair attempt: 1 extra model call
        repair_prompt = REPAIR_PROMPT.format(error=str(err))
        repair_config = get_invoke_config(
            run_id=run_id, phase="research-repair", run_name="campaign-phase1-repair"
        )
        try:
            history = list(messages) + [HumanMessage(content=repair_prompt)]
            repair_reply = model.invoke(history, config=repair_config)
            usage = getattr(repair_reply, "usage_metadata", {}) or {}
            cost_tracker.add_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

            if cost_tracker.is_exceeded():
                return Phase1Result(
                    status="BUDGET_EXCEEDED",
                    angles=None,
                    tool_calls_used=executed_tools,
                    cost_usd=cost_tracker.total_cost_usd,
                )

            repaired_clean = extract_json_str(repair_reply.content)
            repaired_angles = CampaignAngles.model_validate_json(repaired_clean)
            return Phase1Result(
                status="AWAITING_APPROVAL",
                angles=repaired_angles,
                tool_calls_used=executed_tools,
                cost_usd=cost_tracker.total_cost_usd,
                raw_output=repair_reply.content,
            )
        except (ValidationError, ValueError, KeyError, TypeError, RuntimeError):
            return Phase1Result(
                status="FAILED",
                angles=None,
                tool_calls_used=executed_tools,
                cost_usd=cost_tracker.total_cost_usd,
                raw_output=raw_content,
            )


def run_phase2(
    brief: ProductBrief,
    approved_angle: CampaignAngle,
    model: Any,
    run_id: str,
    remaining_tool_calls: int = 15,
    remaining_cost_usd: float = 0.25,
    prior_cost_usd: float = 0.0,
    trace_file: Path | str | None = None,
) -> Phase2Result:
    """Execute Phase 2 advertising copy drafting for the approved angle."""
    settings = get_settings()
    trace_path = trace_file if trace_file is not None else settings.trace_log_path

    if remaining_tool_calls <= 0:
        return Phase2Result(
            status="LIMIT_REACHED", package=None, tool_calls_used=0, cost_usd=prior_cost_usd
        )
    if remaining_cost_usd <= 0:
        return Phase2Result(
            status="BUDGET_EXCEEDED", package=None, tool_calls_used=0, cost_usd=prior_cost_usd
        )

    cost_tracker = CostTracker(
        prior_usd=prior_cost_usd, ceiling_usd=prior_cost_usd + remaining_cost_usd
    )
    trace_logger = TraceLogger(trace_file=trace_path)

    middleware = [
        ToolCallLimitMiddleware(run_limit=remaining_tool_calls, exit_behavior="end"),
        ModelCallLimitMiddleware(run_limit=settings.max_model_calls, exit_behavior="end"),
        CostCeilingMiddleware(cost_tracker=cost_tracker),
        TraceMiddleware(trace_logger=trace_logger, run_id=run_id, cost_tracker=cost_tracker),
    ]

    tools = [draft_copy, analytics_lookup]
    agent = build_agent(
        model=model,
        tools=tools,
        system_prompt=PHASE2_SYSTEM_PROMPT,
        middleware=middleware,
    )

    prompt = (
        "Draft the full advertising copy package for the approved angle:\n"
        f"<product>\nName: {brief.name}\nDescription: {brief.description}\n"
        f"Segment: {brief.segment}\nBudget USD: {brief.budget_usd}\n</product>\n"
        f"<approved_angle>\nTitle: {approved_angle.title}\nPositioning: {approved_angle.positioning}\n"
        f"Target Insight: {approved_angle.target_insight}\nKey Message: {approved_angle.key_message}\n"
        f"Competitor Contrast: {approved_angle.competitor_contrast}\nEvidence: {approved_angle.evidence}\n"
        f"Estimated Reach: {approved_angle.estimated_reach}\n</approved_angle>"
    )

    invoke_config = get_invoke_config(
        run_id=run_id, phase="drafting", run_name="campaign-phase2-drafting"
    )
    invoke_config["recursion_limit"] = 30

    try:
        response = agent.invoke({"messages": [HumanMessage(content=prompt)]}, config=invoke_config)
    except BudgetExceeded:
        return Phase2Result(
            status="BUDGET_EXCEEDED",
            package=None,
            tool_calls_used=0,
            cost_usd=cost_tracker.total_cost_usd,
        )

    messages = response.get("messages", [])
    executed_tools = count_executed_tool_calls(messages)
    limit_hit = was_tool_limit_hit(messages)

    if limit_hit:
        return Phase2Result(
            status="LIMIT_REACHED",
            package=None,
            tool_calls_used=executed_tools,
            cost_usd=cost_tracker.total_cost_usd,
        )

    last_msg = messages[-1] if messages else None
    raw_content = getattr(last_msg, "content", "") if last_msg else ""
    cleaned_json = extract_json_str(raw_content)

    # Validate output against CampaignPackage schema
    try:
        package = CampaignPackage.model_validate_json(cleaned_json)
        return Phase2Result(
            status="COMPLETED",
            package=package,
            tool_calls_used=executed_tools,
            cost_usd=cost_tracker.total_cost_usd,
            raw_output=raw_content,
        )
    except (ValidationError, ValueError) as err:
        # Repair attempt: 1 extra model call
        repair_prompt = REPAIR_PROMPT.format(error=str(err))
        repair_config = get_invoke_config(
            run_id=run_id, phase="drafting-repair", run_name="campaign-phase2-repair"
        )
        try:
            history = list(messages) + [HumanMessage(content=repair_prompt)]
            repair_reply = model.invoke(history, config=repair_config)
            usage = getattr(repair_reply, "usage_metadata", {}) or {}
            cost_tracker.add_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))

            if cost_tracker.is_exceeded():
                return Phase2Result(
                    status="BUDGET_EXCEEDED",
                    package=None,
                    tool_calls_used=executed_tools,
                    cost_usd=cost_tracker.total_cost_usd,
                )

            repaired_clean = extract_json_str(repair_reply.content)
            repaired_pkg = CampaignPackage.model_validate_json(repaired_clean)
            return Phase2Result(
                status="COMPLETED",
                package=repaired_pkg,
                tool_calls_used=executed_tools,
                cost_usd=cost_tracker.total_cost_usd,
                raw_output=repair_reply.content,
            )
        except (ValidationError, ValueError, KeyError, TypeError, RuntimeError):
            return Phase2Result(
                status="FAILED",
                package=None,
                tool_calls_used=executed_tools,
                cost_usd=cost_tracker.total_cost_usd,
                raw_output=raw_content,
            )
