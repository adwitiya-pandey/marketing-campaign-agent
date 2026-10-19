"""Tests for run persistence, transitions, and state machine integrity."""

import pytest

from campaign.models import (
    CampaignAngle,
    CampaignAngles,
    CampaignPackage,
    EmailCopy,
    GoogleAdsCopy,
    InstagramCopy,
    ProductBrief,
    RunRecord,
)
from campaign.store import InvalidTransition, RunStore


def sample_brief() -> ProductBrief:
    return ProductBrief(
        name="Smart Bottle",
        description="A stainless steel bottle with hydration tracking.",
        segment="fitness-enthusiasts",
        budget_usd=5000.0,
    )


def sample_angles() -> CampaignAngles:
    angles = []
    for i in range(5):
        angles.append(
            CampaignAngle(
                title=f"Angle Option {i + 1}",
                positioning="Designed for modern active daily commuters.",
                target_insight="Demographics indicate consistent hydration interest.",
                key_message="Drink more water effortlessly every day.",
                evidence=["Search shows demand for insulation"],
                estimated_reach=12000,
                competitor_contrast="Outperforms standard single-wall flasks.",
            )
        )
    return CampaignAngles(angles=angles)


def sample_package() -> CampaignPackage:
    return CampaignPackage(
        angle_title="Angle Option 1",
        google_ads=GoogleAdsCopy(
            headlines=["Headline One", "Headline Two", "Headline Three"],
            descriptions=["First description here.", "Second description here."],
        ),
        instagram=InstagramCopy(
            caption="Stay hydrated throughout your day. #hydrate #fitness #gear",
            hashtags=["#hydrate", "#fitness", "#gear"],
            image_idea="A clean aesthetic desk setup with the bottle.",
        ),
        email=EmailCopy(
            subject="Introducing Your New Hydration Habit",
            preheader="Hydrate smarter every day",
            body="Here is why Brightside EcoBottle changes your daily hydration routine.",
            cta="Explore Bottle",
        ),
    )


def test_create_and_get_run_roundtrip(tmp_path):
    db_file = tmp_path / "runs.db"
    store = RunStore(db_file)

    rec = RunRecord(
        run_id="RUN-20261019-0001",
        user_id="alice_marketing",
        status="AWAITING_APPROVAL",
        product=sample_brief(),
        angles=sample_angles(),
        created_at="2026-10-19T10:00:00Z",
        updated_at="2026-10-19T10:00:00Z",
    )
    store.create_run(rec)

    # Reopen store to test persistence restart
    reopened = RunStore(db_file)
    fetched = reopened.get_run("RUN-20261019-0001")
    assert fetched is not None
    assert fetched.run_id == "RUN-20261019-0001"
    assert fetched.user_id == "alice_marketing"
    assert fetched.status == "AWAITING_APPROVAL"
    assert fetched.angles is not None
    assert len(fetched.angles.angles) == 5
    assert fetched.angles.angles[0].title == "Angle Option 1"
    assert fetched.package is None


def test_valid_and_invalid_transitions(tmp_path):
    store = RunStore(tmp_path / "runs.db")

    # Start run in AWAITING_APPROVAL
    rec = RunRecord(
        run_id="RUN-20261019-0001",
        user_id="alice_marketing",
        status="AWAITING_APPROVAL",
        product=sample_brief(),
        angles=sample_angles(),
        created_at="2026-10-19T10:00:00Z",
        updated_at="2026-10-19T10:00:00Z",
    )
    store.create_run(rec)

    # Valid transition: AWAITING_APPROVAL -> COMPLETED
    pkg = sample_package()
    updated = store.transition_run(
        "RUN-20261019-0001",
        "COMPLETED",
        selected_index=0,
        package=pkg,
        tool_calls_used=5,
        cost_usd=0.015,
    )
    assert updated.status == "COMPLETED"
    assert updated.selected_index == 0
    assert updated.package is not None
    assert updated.package.angle_title == "Angle Option 1"
    assert updated.tool_calls_used == 5

    # Invalid transition: from COMPLETED -> REJECTED (terminal state)
    with pytest.raises(InvalidTransition):
        store.transition_run("RUN-20261019-0001", "REJECTED")

    # Invalid transition: from COMPLETED -> AWAITING_APPROVAL
    with pytest.raises(InvalidTransition):
        store.transition_run("RUN-20261019-0001", "AWAITING_APPROVAL")


def test_rejection_and_bounds_transitions(tmp_path):
    store = RunStore(tmp_path / "runs.db")

    # Run 2: rejected
    rec2 = RunRecord(
        run_id="RUN-20261019-0002",
        user_id="bob_lead",
        status="AWAITING_APPROVAL",
        product=sample_brief(),
        angles=sample_angles(),
        created_at="2026-10-19T10:00:00Z",
        updated_at="2026-10-19T10:00:00Z",
    )
    store.create_run(rec2)
    rej = store.transition_run("RUN-20261019-0002", "REJECTED")
    assert rej.status == "REJECTED"

    # Terminal state cannot be re-approved
    with pytest.raises(InvalidTransition):
        store.transition_run("RUN-20261019-0002", "COMPLETED")

    # Run 3: limit reached
    rec3 = RunRecord(
        run_id="RUN-20261019-0003",
        user_id="charlie_pm",
        status="AWAITING_APPROVAL",
        product=sample_brief(),
        angles=sample_angles(),
        created_at="2026-10-19T10:00:00Z",
        updated_at="2026-10-19T10:00:00Z",
    )
    store.create_run(rec3)
    lim = store.transition_run("RUN-20261019-0003", "LIMIT_REACHED")
    assert lim.status == "LIMIT_REACHED"


def test_sql_injection_defense_in_user_id(tmp_path):
    """Test SQL injection defense: parameterized SQL + regex rejection."""
    store = RunStore(tmp_path / "runs.db")

    malicious_user = "alice'; DROP TABLE runs; --"

    # 1. Pydantic regex validator in RunRecord rejects malicious user_id before it hits DB
    with pytest.raises(ValueError):
        RunRecord(
            run_id="RUN-20261019-0009",
            user_id=malicious_user,
            status="AWAITING_APPROVAL",
            product=sample_brief(),
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )

    # 2. Even if passed directly to rate limiter query, parameterization treats it as literal string
    store.record_rate_event(malicious_user, 1000.0)
    count = store.count_rate_events(malicious_user, 900.0)
    assert count == 1

    # Verify runs table was not dropped
    assert store.get_run("RUN-20261019-0001") is None  # Table intact
