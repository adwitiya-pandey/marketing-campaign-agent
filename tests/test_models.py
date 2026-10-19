"""Tests for domain models and contracts."""

import pytest
from pydantic import ValidationError

from campaign.models import (
    AnalyticsLookupArgs,
    CampaignAngle,
    CampaignAngles,
    CampaignPackage,
    DraftCopyArgs,
    EmailCopy,
    GoogleAdsCopy,
    InstagramCopy,
    ProductBrief,
    RunRecord,
    SqlQueryArgs,
    WebSearchArgs,
)


def valid_angle(title: str = "Eco Comfort") -> dict:
    return {
        "title": title,
        "positioning": "The sustainable hydration solution for modern active professionals on the go.",
        "target_insight": "SQL shows 68% of eco-conscious users buy high-capacity water bottles regularly.",
        "key_message": "Stay hydrated cleanly and sustainably with Brightside EcoBottle.",
        "evidence": [
            "Search shows top competitor lacks insulated lid",
            "Customers favor 24oz capacity",
        ],
        "estimated_reach": 24500,
        "competitor_contrast": "Unlike HydroX, keeps drinks chilled 24h with zero plastic parts.",
    }


def test_product_brief_valid():
    brief = ProductBrief(
        name="Smart Bottle",
        description="A stainless steel bottle with hydration tracking.",
        segment="fitness-enthusiasts",
        budget_usd=5000.0,
    )
    assert brief.name == "Smart Bottle"
    assert brief.budget_usd == 5000.0


def test_product_brief_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ProductBrief(
            name="Smart Bottle",
            description="A stainless steel bottle with hydration tracking.",
            segment="fitness-enthusiasts",
            extra_field="disallowed",
        )


def test_product_brief_bounds():
    with pytest.raises(ValidationError):
        ProductBrief(name="A", description="Too short", segment="fitness-enthusiasts")
    with pytest.raises(ValidationError):
        ProductBrief(
            name="Valid Name",
            description="Valid description here.",
            segment="invalid-segment",  # type: ignore
        )
    with pytest.raises(ValidationError):
        ProductBrief(
            name="Valid Name",
            description="Valid description here.",
            segment="fitness-enthusiasts",
            budget_usd=50.0,  # Below 100
        )


def test_campaign_angle_valid():
    angle = CampaignAngle(**valid_angle())
    assert angle.title == "Eco Comfort"
    assert angle.estimated_reach == 24500


def test_campaign_angle_extra_field():
    data = valid_angle()
    data["extra"] = 123
    with pytest.raises(ValidationError):
        CampaignAngle(**data)


def test_campaign_angle_evidence_bounds():
    data = valid_angle()
    data["evidence"] = []
    with pytest.raises(ValidationError):
        CampaignAngle(**data)

    data = valid_angle()
    data["evidence"] = ["a" * 201]
    with pytest.raises(ValidationError):
        CampaignAngle(**data)


def test_campaign_angles_exactly_5():
    # 4 angles - should fail
    four_angles = [valid_angle(f"Angle {i}") for i in range(4)]
    with pytest.raises(ValidationError):
        CampaignAngles(angles=[CampaignAngle(**a) for a in four_angles])

    # 5 angles - should pass
    five_angles = [valid_angle(f"Angle {i}") for i in range(5)]
    angles_obj = CampaignAngles(angles=[CampaignAngle(**a) for a in five_angles])
    assert len(angles_obj.angles) == 5

    # 6 angles - should fail
    six_angles = [valid_angle(f"Angle {i}") for i in range(6)]
    with pytest.raises(ValidationError):
        CampaignAngles(angles=[CampaignAngle(**a) for a in six_angles])


def test_campaign_angles_distinct_titles_rule():
    # Duplicate titles with different case
    dup_angles = [valid_angle("Urban Commuter") for _ in range(5)]
    dup_angles[1]["title"] = "urban commuter"
    with pytest.raises(ValidationError, match="distinct"):
        CampaignAngles(angles=[CampaignAngle(**a) for a in dup_angles])


def test_google_ads_copy_constraints():
    # Valid
    ads = GoogleAdsCopy(
        headlines=["Headline 1", "Headline 2", "Headline 3"],
        descriptions=["Description number one.", "Description number two."],
    )
    assert len(ads.headlines) == 3

    # Headline too long (> 30)
    with pytest.raises(ValidationError):
        GoogleAdsCopy(
            headlines=["Headline that is definitely way too long for Google Ads", "H2", "H3"],
            descriptions=["D1", "D2"],
        )

    # Wrong number of headlines
    with pytest.raises(ValidationError):
        GoogleAdsCopy(
            headlines=["H1", "H2"],
            descriptions=["D1", "D2"],
        )


def test_instagram_copy_constraints():
    # Valid
    insta = InstagramCopy(
        caption="Stay hydrated throughout your busiest days. #hydrate #fitness #brightside",
        hashtags=["#hydrate", "#fitness", "#brightside"],
        image_idea="A sleek bottle on a granite desk next to a laptop.",
    )
    assert len(insta.hashtags) == 3

    # Invalid hashtag (missing # or special characters or newline)
    with pytest.raises(ValidationError):
        InstagramCopy(
            caption="Valid caption",
            hashtags=["hydrate", "#fitness", "#brightside"],
            image_idea="Image idea",
        )

    with pytest.raises(ValidationError):
        InstagramCopy(
            caption="Valid caption",
            hashtags=["#hydrate\n", "#fitness", "#brightside"],
            image_idea="Image idea",
        )

    # Hashtag count out of bounds (<3 or >8)
    with pytest.raises(ValidationError):
        InstagramCopy(
            caption="Valid caption",
            hashtags=["#h1", "#h2"],
            image_idea="Image idea",
        )


def test_email_copy_constraints():
    email = EmailCopy(
        subject="Your New Hydration Partner",
        preheader="Discover how to stay energized all day",
        body="Hey there, hydration matters for productivity. Discover our bottle today.",
        cta="Shop Now",
    )
    assert email.cta == "Shop Now"

    # Subject too long (> 60)
    with pytest.raises(ValidationError):
        EmailCopy(
            subject="x" * 61,
            preheader="p",
            body="b",
            cta="c",
        )


def test_campaign_package_nested():
    pkg = CampaignPackage(
        angle_title="Eco Comfort",
        google_ads=GoogleAdsCopy(
            headlines=["H1", "H2", "H3"],
            descriptions=["D1", "D2"],
        ),
        instagram=InstagramCopy(
            caption="Caption here",
            hashtags=["#tag1", "#tag2", "#tag3"],
            image_idea="Image idea",
        ),
        email=EmailCopy(
            subject="Subj",
            preheader="Pre",
            body="Body text",
            cta="Click",
        ),
    )
    assert pkg.angle_title == "Eco Comfort"


def test_tool_args_schemas():
    # WebSearchArgs
    assert WebSearchArgs(query="smart water bottle").query == "smart water bottle"
    with pytest.raises(ValidationError):
        WebSearchArgs(query="ab")  # min 3

    # SqlQueryArgs
    assert SqlQueryArgs(query="SELECT * FROM customers").query == "SELECT * FROM customers"
    with pytest.raises(ValidationError):
        SqlQueryArgs(query="SELECT 1")  # min 10

    # AnalyticsLookupArgs
    lookup = AnalyticsLookupArgs(segment="students", channel="instagram", budget_usd=500.0)
    assert lookup.budget_usd == 500.0
    with pytest.raises(ValidationError):
        AnalyticsLookupArgs(segment="students", channel="instagram", budget_usd=10.0)  # min 50

    # DraftCopyArgs
    draft = DraftCopyArgs(
        channel="email",
        fields={"subject": "S", "body": "B"},
    )
    assert draft.channel == "email"


def test_run_record_id_patterns():
    brief = ProductBrief(
        name="Smart Bottle",
        description="A stainless steel bottle with hydration tracking.",
        segment="fitness-enthusiasts",
    )

    # Valid record
    rec = RunRecord(
        run_id="RUN-20261019-0001",
        user_id="alice_marketing",
        status="AWAITING_APPROVAL",
        product=brief,
        created_at="2026-10-19T10:00:00Z",
        updated_at="2026-10-19T10:00:00Z",
    )
    assert rec.run_id == "RUN-20261019-0001"
    assert rec.user_id == "alice_marketing"

    # Trailing newline in run_id
    with pytest.raises(ValidationError, match="Invalid run_id"):
        RunRecord(
            run_id="RUN-20261019-0001\n",
            user_id="alice_marketing",
            status="AWAITING_APPROVAL",
            product=brief,
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )

    # Non-ASCII digits in run_id (Unicode full-width digits)
    with pytest.raises(ValidationError, match="Invalid run_id"):
        RunRecord(
            run_id="RUN-２０２６１０１９-0001",
            user_id="alice_marketing",
            status="AWAITING_APPROVAL",
            product=brief,
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )

    # Trailing newline in user_id
    with pytest.raises(ValidationError, match="Invalid user_id"):
        RunRecord(
            run_id="RUN-20261019-0001",
            user_id="alice\n",
            status="AWAITING_APPROVAL",
            product=brief,
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )

    # Non-ASCII character in user_id
    with pytest.raises(ValidationError, match="Invalid user_id"):
        RunRecord(
            run_id="RUN-20261019-0001",
            user_id="alice_é",
            status="AWAITING_APPROVAL",
            product=brief,
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )

    # Starting with non-letter
    with pytest.raises(ValidationError, match="Invalid user_id"):
        RunRecord(
            run_id="RUN-20261019-0001",
            user_id="1alice",
            status="AWAITING_APPROVAL",
            product=brief,
            created_at="2026-10-19T10:00:00Z",
            updated_at="2026-10-19T10:00:00Z",
        )
