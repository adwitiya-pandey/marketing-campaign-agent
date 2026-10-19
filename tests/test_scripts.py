"""Tests for scripts (demo_run.py, explain_run.py, cost_report.py)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from campaign.config import Settings
from campaign.models import ProductBrief
from campaign.service import CampaignService
from campaign.store import RunStore
from scripts.cost_report import generate_cost_report
from scripts.demo_run import main as demo_main
from scripts.explain_run import explain_run


def test_demo_run_script_executes_successfully() -> None:
    """Verify demo_run.py main() executes without error and exits 0."""
    code = demo_main()
    assert code == 0


def test_explain_run_contains_angles_and_tool_calls(tmp_path: Path) -> None:
    """Verify explain_run prints each angle title and executed tool calls."""
    db_path = tmp_path / "test_runs.db"
    trace_path = tmp_path / "test_trace.jsonl"
    settings = Settings(
        llm_mode="scripted",
        runs_db=db_path,
        trace_log_path=trace_path,
    )
    store = RunStore(db_path=db_path)
    service = CampaignService(store=store, settings=settings)

    brief = ProductBrief(
        name="Brightside Smart Water Bottle",
        description="Smart water bottle with glow alerts and Bluetooth tracking.",
        segment="young-professionals",
        budget_usd=5000.0,
    )

    res1 = service.start_run(user_id="USR-explainer", brief=brief)
    assert res1.run_id is not None
    res2 = service.approve_angle(run_id=res1.run_id, selected_index=0, user_id="USR-mgr")
    assert res2.status == "COMPLETED"

    # Capture stdout of explain_run
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = explain_run(res1.run_id, trace_file=trace_path, store=store, settings=settings)

    assert code == 0
    output = captured.getvalue()

    # Check each angle title is in output
    for angle in res1.angles.angles:
        assert angle.title in output

    # Check tool calls are in output
    assert "web_search" in output
    assert "sql_query" in output
    assert "analytics_lookup" in output
    assert "draft_copy" in output
    assert "Smart Hydration for Busy Professionals" in output


def test_explain_run_missing_id_returns_error(tmp_path: Path) -> None:
    """Verify explain_run returns code 1 if run_id does not exist."""
    db_path = tmp_path / "test_runs.db"
    settings = Settings(runs_db=db_path)
    code = explain_run("RUN-99999999-9999", settings=settings)
    assert code == 1


def test_cost_report_generates_markdown_with_caveat(tmp_path: Path) -> None:
    """Verify generate_cost_report writes markdown file with notional caveat."""
    out_file = tmp_path / "cost_report.md"
    db_path = tmp_path / "test_runs.db"
    trace_path = tmp_path / "test_trace.jsonl"

    settings = Settings(
        llm_mode="scripted",
        runs_db=db_path,
        trace_log_path=trace_path,
    )
    store = RunStore(db_path=db_path)
    service = CampaignService(store=store, settings=settings)

    brief = ProductBrief(
        name="EcoBento Reusable Box",
        description="Modular stainless steel leak-proof lunch box container.",
        segment="young-professionals",
        budget_usd=3000.0,
    )
    res = service.start_run(user_id="USR-reporter", brief=brief)
    service.approve_angle(run_id=res.run_id, selected_index=0, user_id="USR-mgr")

    code = generate_cost_report(output_file=out_file, store=store, settings=settings)

    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")

    assert "Notional Cost Caveat" in content
    assert "SPEC section 10" in content
    assert "Tool Performance Breakdown" in content
    assert "web_search" in content
    assert res.run_id in content
