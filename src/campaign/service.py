"""Two-phase campaign service orchestrating agent runs, human approval, and bounds."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from campaign.agent import run_phase1, run_phase2
from campaign.config import get_settings
from campaign.llm import get_chat_model
from campaign.logging_setup import current_phase, current_run_id, get_logger
from campaign.models import (
    USER_ID_REGEX,
    ProductBrief,
    RunRecord,
    RunStatus,
)
from campaign.ratelimit import RateLimiter
from campaign.sanitize import sanitize_brief
from campaign.store import InvalidTransition, RunStore

logger = get_logger("campaign.service")


@dataclass
class ServiceResult:
    """Service operation result with transparent attribute forwarding to RunRecord."""

    status: RunStatus | str
    run: RunRecord | None = None
    wait_seconds: float = 0.0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        if self.run is not None and hasattr(self.run, name):
            return getattr(self.run, name)
        raise AttributeError(f"'ServiceResult' object has no attribute '{name}'")


def generate_run_id() -> str:
    """Generate a valid RUN-YYYYMMDD-XXXX run ID matching ^RUN-[0-9]{8}-[0-9]{4}$."""
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    suffix = random.randint(1000, 9999)
    return f"RUN-{date_str}-{suffix}"


class CampaignService:
    """Orchestrates Phase 1 research, the human approval gate, and Phase 2 drafting."""

    def __init__(
        self,
        store: RunStore | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.store = store if store is not None else RunStore()
        self.rate_limiter = (
            rate_limiter if rate_limiter is not None else RateLimiter(store=self.store)
        )

    def start_run(
        self,
        user_id: str,
        brief: ProductBrief,
        model: Any = None,
    ) -> ServiceResult:
        """Start a new campaign run: rate limit -> sanitise -> Phase 1 agent."""
        if not USER_ID_REGEX.fullmatch(user_id):
            raise ValueError(
                f"Invalid user_id '{user_id}': must match ^[A-Za-z][A-Za-z0-9_.-]{{1,31}}$"
            )

        # 1. Rate limiting check
        allowed, wait_s = self.rate_limiter.check_allowed(user_id)
        if not allowed:
            logger.info("run_rate_limited", user_id=user_id, wait_seconds=wait_s)
            return ServiceResult(status="RATE_LIMITED", wait_seconds=wait_s)

        # 2. Sanitise brief (raises HostileInputError on injection)
        clean_brief = sanitize_brief(brief)

        # Consume rate limit slot
        self.rate_limiter.record_run(user_id)

        # 3. Initialize run identifiers and contextvars
        run_id = generate_run_id()
        current_run_id.set(run_id)
        current_phase.set("research")

        now_iso = datetime.now(UTC).isoformat()
        chat_model = model if model is not None else get_chat_model()

        # 4. Execute Phase 1
        settings = get_settings()
        p1 = run_phase1(
            brief=clean_brief,
            model=chat_model,
            run_id=run_id,
            max_tool_calls=settings.max_tool_calls,
            cost_ceiling_usd=settings.cost_ceiling_usd,
        )

        record = RunRecord(
            run_id=run_id,
            user_id=user_id,
            status=p1.status,
            product=clean_brief,
            angles=p1.angles,
            tool_calls_used=p1.tool_calls_used,
            cost_usd=round(p1.cost_usd, 6),
            created_at=now_iso,
            updated_at=now_iso,
        )
        self.store.create_run(record)
        logger.info(
            "phase1_completed",
            run_id=run_id,
            status=p1.status,
            tool_calls_used=p1.tool_calls_used,
            cost_usd=p1.cost_usd,
        )

        return ServiceResult(status=p1.status, run=self.store.get_run(run_id))

    def approve_angle(
        self,
        run_id: str,
        index: int,
        reviewer: str,
        model: Any = None,
    ) -> ServiceResult:
        """Approve an angle by index: human gate -> Phase 2 drafting."""
        if not USER_ID_REGEX.fullmatch(reviewer):
            raise ValueError(f"Invalid reviewer ID '{reviewer}'")

        if index < 0 or index > 4:
            raise IndexError(f"Angle index must be between 0 and 4, got {index}")

        run = self.store.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found")

        if run.status != "AWAITING_APPROVAL":
            raise InvalidTransition(
                f"Cannot approve run in status '{run.status}'. Must be 'AWAITING_APPROVAL'"
            )

        if not run.angles or len(run.angles.angles) <= index:
            raise ValueError(f"Run {run_id} does not contain stored angle at index {index}")

        # S10: Read approved angle from store, never take angle content from UI payload
        approved_angle = run.angles.angles[index]

        settings = get_settings()
        remaining_tools = settings.max_tool_calls - run.tool_calls_used
        remaining_cost = max(0.0, settings.cost_ceiling_usd - run.cost_usd)

        # Check remaining bounds before starting Phase 2
        if remaining_tools <= 0:
            updated = self.store.transition_run(
                run_id,
                "LIMIT_REACHED",
                selected_index=index,
            )
            return ServiceResult(status="LIMIT_REACHED", run=updated)

        if remaining_cost <= 0.0:
            updated = self.store.transition_run(
                run_id,
                "BUDGET_EXCEEDED",
                selected_index=index,
            )
            return ServiceResult(status="BUDGET_EXCEEDED", run=updated)

        current_run_id.set(run_id)
        current_phase.set("drafting")

        chat_model = model if model is not None else get_chat_model()
        p2 = run_phase2(
            brief=run.product,
            approved_angle=approved_angle,
            model=chat_model,
            run_id=run_id,
            remaining_tool_calls=remaining_tools,
            remaining_cost_usd=remaining_cost,
            prior_cost_usd=run.cost_usd,
        )

        updated_tools = run.tool_calls_used + p2.tool_calls_used
        updated_cost = round(p2.cost_usd, 6)

        updated_run = self.store.transition_run(
            run_id,
            p2.status,
            selected_index=index,
            package=p2.package,
            tool_calls_used=updated_tools,
            cost_usd=updated_cost,
        )

        logger.info(
            "phase2_completed",
            run_id=run_id,
            status=p2.status,
            tool_calls_used=updated_tools,
            cost_usd=updated_cost,
        )
        return ServiceResult(status=p2.status, run=updated_run)

    def reject_run(self, run_id: str, reviewer: str) -> ServiceResult:
        """Reject all proposed angles and terminate run."""
        if not USER_ID_REGEX.fullmatch(reviewer):
            raise ValueError(f"Invalid reviewer ID '{reviewer}'")

        run = self.store.get_run(run_id)
        if not run:
            raise KeyError(f"Run {run_id} not found")

        if run.status != "AWAITING_APPROVAL":
            raise InvalidTransition(
                f"Cannot reject run in status '{run.status}'. Must be 'AWAITING_APPROVAL'"
            )

        updated = self.store.transition_run(run_id, "REJECTED")
        logger.info("run_rejected", run_id=run_id, reviewer=reviewer)
        return ServiceResult(status="REJECTED", run=updated)
