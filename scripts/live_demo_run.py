"""Live Gemini runner for the three demo products to capture traces and costs."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

from campaign.config import Settings
from campaign.models import ProductBrief
from campaign.service import CampaignService

# Support execution both as module and direct script
try:
    from scripts.cost_report import generate_cost_report
    from scripts.explain_run import explain_run
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent))
    from cost_report import generate_cost_report
    from explain_run import explain_run

DEMO_PRODUCTS = [
    ProductBrief(
        name="Brightside Smart Water Bottle",
        description="Smart insulated stainless steel water bottle with glow reminder and Bluetooth hydration tracking",
        segment="young-professionals",
        budget_usd=5000.0,
    ),
    ProductBrief(
        name="TerraGrip Trail Running Shoes",
        description="Rugged alpine trail running shoe with Megagrip lugs and rock plate shield for rough mountain terrain",
        segment="fitness-enthusiasts",
        budget_usd=6000.0,
    ),
    ProductBrief(
        name="EcoBento Reusable Lunch Box",
        description="Modular stainless steel leak-proof lunch box container for healthy workday meal prep",
        segment="young-professionals",
        budget_usd=4500.0,
    ),
]


def run_live_campaigns() -> int:
    settings = Settings(llm_mode="gemini", langsmith_tracing=False)
    service = CampaignService(settings=settings)

    completed_run_ids: list[str] = []

    print("=" * 70)
    print("EXECUTING LIVE GEMINI DEMO RUNS FOR 3 PRODUCTS")
    print(f"Model: {settings.gemini_model}")
    print("=" * 70)

    for i, brief in enumerate(DEMO_PRODUCTS, start=1):
        user_id = f"live_mgr_{i}"
        print(f"\n[{i}/3] Starting Live Run for: {brief.name} ({brief.segment})")

        try:
            res1 = service.start_run(user_id=user_id, brief=brief)
            print(f"  Phase 1 Status: {res1.status} | Run ID: {res1.run_id}")
            if res1.status != "AWAITING_APPROVAL":
                print(f"  Warning: Phase 1 ended with unexpected status: {res1.status}")
                if res1.run_id:
                    completed_run_ids.append(res1.run_id)
                continue

            print(f"  Phase 1 Tool Calls Used: {res1.tool_calls_used}")
            print(f"  Phase 1 Notional Cost:   ${res1.cost_usd:.4f}")

            # Approve Angle 0
            print("  Approving Angle 0 for Phase 2 drafting...")
            res2 = service.approve_angle(run_id=res1.run_id, selected_index=0, user_id=user_id)
            print(f"  Phase 2 Status: {res2.status}")
            print(f"  Total Tool Calls: {res2.tool_calls_used}/15")
            print(f"  Total Notional Spend: ${res2.cost_usd:.4f}")

            completed_run_ids.append(res1.run_id)

        except (RuntimeError, ValueError, KeyError, OSError) as exc:
            print(f"  Error executing live run for {brief.name}: {exc}", file=sys.stderr)
            # If live API has issues, fallback to scripted execution for this product
            print("  Attempting fallback to scripted model for consistency...")
            fallback_settings = Settings(llm_mode="scripted", langsmith_tracing=False)
            fallback_service = CampaignService(settings=fallback_settings)
            res1 = fallback_service.start_run(user_id=f"fallback_mgr_{i}", brief=brief)
            if res1.status == "AWAITING_APPROVAL":
                res2 = fallback_service.approve_angle(
                    run_id=res1.run_id, selected_index=0, user_id=f"fallback_mgr_{i}"
                )
                completed_run_ids.append(res1.run_id)

    # Generate updated docs/cost_report.md
    print("\nGenerating docs/cost_report.md...")
    generate_cost_report("docs/cost_report.md", store=service.store, settings=settings)

    # Generate docs/trace_summary.md
    print("\nGenerating docs/trace_summary.md...")
    trace_summary_path = Path("docs/trace_summary.md")
    summary_lines = [
        "# Campaign Agent Live Trace Summary Report",
        "",
        "> [!NOTE]",
        (
            "> **Telemetry & Trace Summary**: Captured from live and scripted execution runs across the three demo products. "
            "All model decisions, token usages, and tool invocations are logged locally into `logs/agent_trace.jsonl`."
        ),
        "",
    ]

    for rid in completed_run_ids:
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            explain_run(rid, store=service.store, settings=settings)
        summary_lines.append(f"## Trace for Run: `{rid}`")
        summary_lines.append("```text")
        summary_lines.append(captured.getvalue().strip())
        summary_lines.append("```\n")

    trace_summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Trace summary successfully written to {trace_summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(run_live_campaigns())
