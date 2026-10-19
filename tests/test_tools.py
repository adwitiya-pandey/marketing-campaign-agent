"""Tests for agent tools with mocked and fixture backends."""

import json

from campaign.tools.analytics_lookup import analytics_lookup
from campaign.tools.draft_copy import draft_copy
from campaign.tools.sql_query import sql_query
from campaign.tools.web_search import web_search
from scripts.build_db import build_database


def test_web_search_valid_and_flagged_snippet():
    # Search for smart water bottle: should include normal results and flagged injection fixture
    res_str = web_search.invoke({"query": "smart water bottle"})
    data = json.loads(res_str)

    assert "results" in data
    results = data["results"]
    assert len(results) > 0
    assert len(results) <= 5

    # Snippets must be wrapped in <untrusted>
    for r in results:
        assert r["snippet"].startswith("<untrusted>")
        assert r["snippet"].endswith("</untrusted>")

    # At least one result flagged for prompt injection
    flagged_results = [r for r in results if r["flagged"] is True]
    assert len(flagged_results) >= 1
    assert (
        "SYSTEM" in flagged_results[0]["snippet"].upper()
        or "OVERRIDE" in flagged_results[0]["snippet"].upper()
    )


def test_web_search_unknown_query():
    res_str = web_search.invoke({"query": "completely unknown product query 123456"})
    data = json.loads(res_str)
    assert "results" in data
    assert data["results"] == []
    assert "message" in data


def test_sql_query_valid(tmp_path):
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)

    # Valid SELECT query
    res_str = sql_query.invoke({"query": "SELECT customer_id, segment FROM customers LIMIT 5"})
    data = json.loads(res_str)

    assert "columns" in data
    assert "rows" in data
    assert len(data["rows"]) == 5
    assert data["columns"] == ["customer_id", "segment"]
    assert data["truncated"] is False


def test_sql_query_rejection():
    # Hostile stacked query
    res_str = sql_query.invoke({"query": "SELECT * FROM customers; DROP TABLE customers"})
    data = json.loads(res_str)

    assert "error" in data
    assert data["error"].startswith("REJECTED:")
    assert "STACKED_STATEMENTS" in data["error"] or "SEMICOLON" in data["error"]


def test_sql_query_table_outside_allowlist():
    res_str = sql_query.invoke({"query": "SELECT * FROM super_secret_passwords"})
    data = json.loads(res_str)

    assert "error" in data
    assert data["error"].startswith("REJECTED: TABLE_NOT_ALLOWED")


def test_sql_query_row_capping(tmp_path):
    # Query without explicit LIMIT: tool validates and caps rows at 50
    res_str = sql_query.invoke({"query": "SELECT customer_id FROM customers"})
    data = json.loads(res_str)

    assert "rows" in data
    assert len(data["rows"]) == 50
    assert data["truncated"] is False or data["truncated"] is True


def test_analytics_lookup_valid():
    res_str = analytics_lookup.invoke(
        {"segment": "students", "channel": "instagram", "budget_usd": 1250.0}
    )
    data = json.loads(res_str)

    assert data["estimated_reach"] == 24000
    assert data["assumptions"] == "mock"


def test_analytics_lookup_invalid_args():
    res_str = analytics_lookup.invoke(
        {"segment": "students", "channel": "instagram", "budget_usd": 10.0}  # Below 50.0
    )
    data = json.loads(res_str)
    assert "error" in data


def test_draft_copy_google_ads_success():
    fields = {
        "headlines": ["Headline One", "Headline Two", "Headline Three"],
        "descriptions": ["First description of the product.", "Second description of the product."],
    }
    res_str = draft_copy.invoke({"channel": "google_ads", "fields": fields})
    data = json.loads(res_str)

    assert data["ok"] is True
    assert data["copy"]["headlines"] == fields["headlines"]


def test_draft_copy_compliance_rejection():
    # Contains banned claim 'guaranteed'
    fields = {
        "headlines": ["Guaranteed Results", "Headline Two", "Headline Three"],
        "descriptions": ["First description.", "Second description."],
    }
    res_str = draft_copy.invoke({"channel": "google_ads", "fields": fields})
    data = json.loads(res_str)

    assert data["ok"] is False
    assert "errors" in data
    assert any("guaranteed" in err.lower() for err in data["errors"])


def test_draft_copy_invalid_channel():
    res_str = draft_copy.invoke({"channel": "billboard", "fields": {}})  # type: ignore
    data = json.loads(res_str)
    assert data["ok"] is False
    assert "errors" in data
