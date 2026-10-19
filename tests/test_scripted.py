"""Tests for scripted demo model and multi-product offline execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from campaign.config import Settings
from campaign.models import ProductBrief
from campaign.scripted import SCRIPTED_ANGLES
from campaign.service import CampaignService
from campaign.store import RunStore


@pytest.mark.parametrize(
    ("product_name", "description", "segment", "expected_key"),
    [
        (
            "Brightside Smart Water Bottle",
            "Insulated stainless steel smart water bottle with glow reminder and tracking.",
            "young-professionals",
            "smart-water-bottle",
        ),
        (
            "TerraGrip Trail Running Shoes",
            "Rugged alpine trail running shoe with Megagrip lugs and rock plate shield.",
            "fitness-enthusiasts",
            "trail-running-shoes",
        ),
        (
            "EcoBento Lunch Box",
            "Modular stainless steel leak-proof lunch box container for meal prep.",
            "young-professionals",
            "reusable-lunch-box",
        ),
    ],
)
def test_scripted_model_all_three_products_complete(
    tmp_path: Path,
    product_name: str,
    description: str,
    segment: str,
    expected_key: str,
) -> None:
    """Verify demo flow for all three products ends COMPLETED offline."""
    db_path = tmp_path / "test_runs.db"
    settings = Settings(
        llm_mode="scripted",
        runs_db=db_path,
        trace_log_path=tmp_path / "test_trace.jsonl",
    )
    store = RunStore(db_path=db_path)
    service = CampaignService(store=store, settings=settings)

    brief = ProductBrief(
        name=product_name,
        description=description,
        segment=segment,
        budget_usd=4000.0,
    )

    # Phase 1
    res1 = service.start_run(user_id="USR-tester", brief=brief)
    assert res1.status == "AWAITING_APPROVAL"
    assert res1.run is not None
    assert res1.angles is not None
    assert len(res1.angles.angles) == 5

    # Angles match expected scripted angles
    expected_titles = [a["title"] for a in SCRIPTED_ANGLES[expected_key]]
    actual_titles = [a.title for a in res1.angles.angles]
    assert actual_titles == expected_titles

    # Phase 2: Approve angle 0
    res2 = service.approve_angle(
        run_id=res1.run_id,
        selected_index=0,
        user_id="USR-manager",
    )
    assert res2.status == "COMPLETED"
    assert res2.run is not None
    assert res2.package is not None
    assert res2.package.angle_title == expected_titles[0]
    assert len(res2.package.google_ads.headlines) == 3
    assert len(res2.package.instagram.hashtags) >= 3
    assert res2.package.email.subject != ""


def test_scripted_model_injection_in_fixtures_does_not_alter_angles(tmp_path: Path) -> None:
    """Verify fixture injection payload is safely handled and does not alter angles."""
    # Read fixtures to verify injection payload is present in search fixtures
    fixture_path = Path("data/fixtures/search.json")
    assert fixture_path.exists()
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Verify injection payload exists in the fixture data
    has_injection = False
    for results in fixtures.values():
        for res in results:
            snippet = res.get("snippet", "")
            title = res.get("title", "")
            if (
                "SYSTEM" in snippet
                or "Ignore all previous" in snippet
                or "System Override" in title
            ):
                has_injection = True
                break
        if has_injection:
            break
    assert has_injection, "Expected prompt injection snippet in search.json fixtures"

    # Now execute smart bottle run in scripted mode
    db_path = tmp_path / "test_runs.db"
    settings = Settings(
        llm_mode="scripted",
        runs_db=db_path,
        trace_log_path=tmp_path / "test_trace.jsonl",
    )
    store = RunStore(db_path=db_path)
    service = CampaignService(store=store, settings=settings)

    brief = ProductBrief(
        name="Brightside Smart Water Bottle",
        description="Smart water bottle with Bluetooth hydration tracking and glow reminders.",
        segment="young-professionals",
        budget_usd=5000.0,
    )

    res1 = service.start_run(user_id="USR-tester", brief=brief)
    assert res1.status == "AWAITING_APPROVAL"
    assert res1.angles is not None

    # Expected titles must remain unchanged and completely uncompromised
    expected_titles = [a["title"] for a in SCRIPTED_ANGLES["smart-water-bottle"]]
    actual_titles = [a.title for a in res1.angles.angles]
    assert actual_titles == expected_titles

    # Verify no angle titles or positioning contain injected phrases
    for angle in res1.angles.angles:
        assert "SYSTEM OVERRIDE" not in angle.title
        assert "HACKED" not in angle.title
        assert "IGNORE PREVIOUS" not in angle.positioning
