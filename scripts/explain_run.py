"""Explain run decisions: join stored campaign angles with agent trace lines."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from campaign.config import get_settings
from campaign.store import RunStore


def explain_run(
    run_id: str,
    trace_file: Path | str | None = None,
    store: RunStore | None = None,
    settings: Any = None,
) -> int:
    cfg = settings if settings is not None else get_settings()
    run_store = store if store is not None else RunStore(db_path=cfg.runs_db)
    run = run_store.get_run(run_id)

    if not run:
        print(f"ERROR: Run '{run_id}' not found in database.", file=sys.stderr)
        return 1

    trace_path = Path(trace_file) if trace_file else Path(cfg.trace_log_path)
    traces: list[dict] = []
    if trace_path.exists():
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if record.get("run_id") == run_id:
                            traces.append(record)
                    except json.JSONDecodeError:
                        continue

    print("=" * 70)
    print(f"EXPLAIN RUN: {run.run_id}")
    print("=" * 70)
    print(f"Status:          {run.status}")
    print(f"Product:         {run.product.name}")
    print(f"Segment:         {run.product.segment}")
    print(f"Tool Calls Used: {run.tool_calls_used}")
    print(
        f"Notional Cost:   ${run.cost_usd:.4f} (Notional: tokens x pricing; free tier bills $0.00)"
    )

    # 1. Executed tool calls
    tool_calls = [t for t in traces if t.get("type") == "tool_call"]
    print(f"\n--- EXECUTED TOOL CALLS ({len(tool_calls)}) ---")
    if not tool_calls:
        print("  (No trace events recorded for this run)")
    else:
        for idx, tc in enumerate(tool_calls, start=1):
            status_str = "OK" if tc.get("ok") else f"FAILED ({tc.get('error_code')})"
            print(
                f"[{idx}] Tool: {tc.get('tool')} | Status: {status_str} | Duration: {tc.get('duration_ms')}ms"
            )
            print(f"    Args: {tc.get('args')}")

    # 2. Campaign angles & evidence grounding
    print("\n--- CAMPAIGN ANGLES & EVIDENCE GROUNDING ---")
    if not run.angles or not run.angles.angles:
        print("  (No angles generated for this run)")
    else:
        for idx, angle in enumerate(run.angles.angles):
            is_selected = " [APPROVED & DRAFTED]" if run.selected_index == idx else ""
            print(f"\nAngle [{idx}]: {angle.title}{is_selected}")
            print(f"  Positioning:         {angle.positioning}")
            print(f"  Target Insight:      {angle.target_insight}")
            print(f"  Key Message:         {angle.key_message}")
            print(f"  Competitor Contrast: {angle.competitor_contrast}")
            print(f"  Estimated Reach:     {angle.estimated_reach:,}")
            print("  Evidence:")
            for ev in angle.evidence:
                print(f"    - {ev}")

    # 3. Drafted Package
    if run.package:
        print("\n--- APPROVED CAMPAIGN PACKAGE ---")
        print(f"Angle Title: {run.package.angle_title}")
        print(
            f"Google Ads:  {len(run.package.google_ads.headlines)} headlines, {len(run.package.google_ads.descriptions)} descriptions"
        )
        print(
            f"Instagram:   {len(run.package.instagram.hashtags)} hashtags, {len(run.package.instagram.caption)} chars caption"
        )
        print(
            f"Email:       '{run.package.email.subject}' ({len(run.package.email.body)} chars body)"
        )

    print("\n" + "=" * 70)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        # Check if any run exists to be user-friendly, else print usage
        settings = get_settings()
        store = RunStore(db_path=settings.runs_db)
        runs = store.list_runs(limit=1)
        if runs:
            print(f"No run_id specified. Defaulting to most recent run: {runs[0].run_id}\n")
            return explain_run(runs[0].run_id)
        print("Usage: uv run python scripts/explain_run.py <RUN_ID>", file=sys.stderr)
        return 1

    run_id = sys.argv[1].strip()
    return explain_run(run_id)


if __name__ == "__main__":
    sys.exit(main())
