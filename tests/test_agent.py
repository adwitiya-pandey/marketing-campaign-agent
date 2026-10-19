"""Tests for agent execution, middleware limits, and repair loop (Tests First)."""

import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from campaign.agent import run_phase1, run_phase2
from campaign.models import (
    CampaignAngle,
    ProductBrief,
)


class FakeToolModel(GenericFakeChatModel):
    """Fake model returning predefined sequence of AIMessages while binding tools."""

    def bind_tools(self, tools, **kwargs):
        return self


def sample_brief() -> ProductBrief:
    return ProductBrief(
        name="Smart Bottle",
        description="A stainless steel bottle with hydration tracking features.",
        segment="fitness-enthusiasts",
        budget_usd=5000.0,
    )


def sample_angles_json() -> str:
    angles = []
    for i in range(5):
        angles.append(
            {
                "title": f"Angle {i + 1}",
                "positioning": "The sustainable hydration solution for modern active professionals.",
                "target_insight": "SQL shows 68% of eco-conscious users buy high-capacity water bottles.",
                "key_message": "Stay hydrated cleanly and sustainably with Brightside EcoBottle.",
                "evidence": ["Search shows top competitor lacks insulated lid"],
                "estimated_reach": 25000,
                "competitor_contrast": "Keeps drinks chilled 24h with zero plastic parts.",
            }
        )
    return json.dumps({"angles": angles})


def sample_package_json() -> str:
    return json.dumps(
        {
            "angle_title": "Angle 1",
            "google_ads": {
                "headlines": ["Headline 1", "Headline 2", "Headline 3"],
                "descriptions": ["First description text.", "Second description text."],
            },
            "instagram": {
                "caption": "Stay hydrated every single day. #hydrate #fitness #brightside",
                "hashtags": ["#hydrate", "#fitness", "#brightside"],
                "image_idea": "A sleek bottle on a granite desk.",
            },
            "email": {
                "subject": "Hydrate Smarter",
                "preheader": "Discover Brightside EcoBottle",
                "body": "Here is why our insulated stainless bottle changes hydration.",
                "cta": "Shop Now",
            },
        }
    )


def test_phase1_happy_path(tmp_path):
    # Model executes web_search, sql_query, analytics_lookup, then outputs 5 angles
    msgs = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "smart water bottle"}, "id": "call_1"}
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "sql_query",
                    "args": {"query": "SELECT customer_id FROM customers LIMIT 5"},
                    "id": "call_2",
                }
            ],
            usage_metadata={"input_tokens": 150, "output_tokens": 30, "total_tokens": 180},
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "analytics_lookup",
                    "args": {
                        "segment": "fitness-enthusiasts",
                        "channel": "instagram",
                        "budget_usd": 5000.0,
                    },
                    "id": "call_3",
                }
            ],
            usage_metadata={"input_tokens": 200, "output_tokens": 40, "total_tokens": 240},
        ),
        AIMessage(
            content=sample_angles_json(),
            usage_metadata={"input_tokens": 300, "output_tokens": 250, "total_tokens": 550},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "AWAITING_APPROVAL"
    assert res.angles is not None
    assert len(res.angles.angles) == 5
    assert res.tool_calls_used == 3
    assert res.cost_usd > 0.0


def test_phase2_happy_path(tmp_path):
    angle = CampaignAngle(
        title="Angle 1",
        positioning="The sustainable hydration solution for modern active professionals.",
        target_insight="SQL shows 68% of eco-conscious users buy high-capacity water bottles.",
        key_message="Stay hydrated cleanly and sustainably with Brightside EcoBottle.",
        evidence=["Search shows top competitor lacks insulated lid"],
        estimated_reach=25000,
        competitor_contrast="Keeps drinks chilled 24h with zero plastic parts.",
    )

    # Model calls draft_copy then outputs full package JSON
    msgs = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "draft_copy",
                    "args": {
                        "channel": "google_ads",
                        "fields": {
                            "headlines": ["H1", "H2", "H3"],
                            "descriptions": ["D1 text here.", "D2 text here."],
                        },
                    },
                    "id": "draft_1",
                }
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 30, "total_tokens": 130},
        ),
        AIMessage(
            content=sample_package_json(),
            usage_metadata={"input_tokens": 200, "output_tokens": 150, "total_tokens": 350},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase2(
        brief=sample_brief(),
        approved_angle=angle,
        model=model,
        run_id="RUN-20261019-0001",
        remaining_tool_calls=12,
        remaining_cost_usd=0.20,
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "COMPLETED"
    assert res.package is not None
    assert res.package.angle_title == "Angle 1"
    assert res.tool_calls_used == 1


def test_phase1_repair_success(tmp_path):
    # Model returns invalid JSON first, receives repair prompt, then returns valid JSON
    bad_json = '{"angles": [{"title": "Only One"}]}'  # Not 5 angles!
    good_json = sample_angles_json()

    msgs = [
        AIMessage(
            content=bad_json,
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        ),
        AIMessage(
            content=good_json,
            usage_metadata={"input_tokens": 200, "output_tokens": 250, "total_tokens": 450},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "AWAITING_APPROVAL"
    assert res.angles is not None
    assert len(res.angles.angles) == 5


def test_phase1_repair_exhausted(tmp_path):
    # Model returns invalid JSON twice -> repair exhausted -> status FAILED
    bad_json = '{"angles": "invalid structure"}'

    msgs = [
        AIMessage(
            content=bad_json,
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        ),
        AIMessage(
            content=bad_json,
            usage_metadata={"input_tokens": 150, "output_tokens": 50, "total_tokens": 200},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "FAILED"
    assert res.angles is None


def test_tool_limit_reached(tmp_path):
    # Model asks for 5 calls when limit is 2
    msgs = [
        AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "args": {"query": f"search {i}"}, "id": f"c_{i}"}],
            usage_metadata={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
        )
        for i in range(5)
    ]
    msgs.append(
        AIMessage(
            content="done",
            usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        )
    )

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        max_tool_calls=2,
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "LIMIT_REACHED"
    assert res.tool_calls_used == 2


def test_cost_ceiling_exceeded(tmp_path):
    # Model returns huge token usage crossing $0.25 ceiling
    # 50,000 output tokens at $7.50/M = $0.375 > $0.25
    msgs = [
        AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "args": {"query": "smart bottle"}, "id": "call_1"}],
            usage_metadata={"input_tokens": 1000, "output_tokens": 50_000, "total_tokens": 51_000},
        ),
        AIMessage(content=sample_angles_json()),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        cost_ceiling_usd=0.25,
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "BUDGET_EXCEEDED"
    assert res.angles is None


def test_tool_invalid_args_handled(tmp_path):
    # Model calls tool with invalid query (too short < 3), gets error, then recovers
    msgs = [
        AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "args": {"query": "a"}, "id": "bad_call"}],
            usage_metadata={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "smart water bottle"}, "id": "good_call"}
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        ),
        AIMessage(
            content=sample_angles_json(),
            usage_metadata={"input_tokens": 200, "output_tokens": 200, "total_tokens": 400},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "AWAITING_APPROVAL"
    assert res.angles is not None
    assert res.tool_calls_used == 2


def test_sql_rejected_then_corrected(tmp_path):
    # Model calls stacked query (rejected), gets error message, then corrects to valid query
    msgs = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "sql_query",
                    "args": {"query": "SELECT * FROM customers; DROP TABLE customers"},
                    "id": "bad_sql",
                }
            ],
            usage_metadata={"input_tokens": 50, "output_tokens": 20, "total_tokens": 70},
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "sql_query",
                    "args": {"query": "SELECT customer_id FROM customers LIMIT 5"},
                    "id": "good_sql",
                }
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        ),
        AIMessage(
            content=sample_angles_json(),
            usage_metadata={"input_tokens": 200, "output_tokens": 200, "total_tokens": 400},
        ),
    ]

    model = FakeToolModel(messages=iter(msgs))
    res = run_phase1(
        brief=sample_brief(),
        model=model,
        run_id="RUN-20261019-0001",
        trace_file=tmp_path / "trace.jsonl",
    )

    assert res.status == "AWAITING_APPROVAL"
    assert res.angles is not None
    assert res.tool_calls_used == 2
