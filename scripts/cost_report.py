"""Cost and tool reliability reporting across campaign agent runs."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from campaign.config import get_settings
from campaign.store import RunStore

NOTIONAL_CAVEAT = (
    "All costs listed in this report are notional estimates calculated from configured token rates "
    "(SPEC section 10: $1.50/1M input tokens, $7.50/1M output tokens). Google Gemini free tier "
    "and scripted demo runs bill $0.00. No actual charges were incurred."
)


@dataclass
class ToolMetrics:
    calls: int = 0
    ok: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return (self.ok / self.calls) if self.calls > 0 else 1.0

    @property
    def avg_duration_ms(self) -> float:
        return (self.total_duration_ms / self.calls) if self.calls > 0 else 0.0


def generate_cost_report(
    output_file: Path | str = "docs/cost_report.md",
    store: RunStore | None = None,
    settings: Any = None,
) -> int:
    cfg = settings if settings is not None else get_settings()
    run_store = store if store is not None else RunStore(db_path=cfg.runs_db)
    runs = run_store.list_runs(limit=500)

    trace_path = Path(cfg.trace_log_path)
    traces: list[dict] = []
    if trace_path.exists():
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        traces.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    # Tool stats aggregation
    tool_stats: dict[str, ToolMetrics] = defaultdict(ToolMetrics)
    for t in traces:
        if t.get("type") == "tool_call":
            tool_name = str(t.get("tool", "unknown"))
            is_ok = bool(t.get("ok", False))
            dur = float(t.get("duration_ms", 0.0))
            metrics = tool_stats[tool_name]
            metrics.calls += 1
            if is_ok:
                metrics.ok += 1
            else:
                metrics.errors += 1
            metrics.total_duration_ms += dur

    total_tool_calls = sum(m.calls for m in tool_stats.values())
    total_tool_ok = sum(m.ok for m in tool_stats.values())
    total_tool_errors = sum(m.errors for m in tool_stats.values())
    overall_tool_success_rate = (total_tool_ok / total_tool_calls) if total_tool_calls > 0 else 1.0

    total_runs = len(runs)
    completed_runs = sum(1 for r in runs if r.status == "COMPLETED")
    total_notional_cost = sum(r.cost_usd for r in runs)
    avg_cost_per_run = (total_notional_cost / total_runs) if total_runs > 0 else 0.0
    avg_tools_per_run = (
        (sum(r.tool_calls_used for r in runs) / total_runs) if total_runs > 0 else 0.0
    )

    # 1. Print to stdout
    print("=" * 70)
    print("CAMPAIGN AGENT - COST & PERFORMANCE REPORT")
    print("=" * 70)
    print(f"\nNOTE: {NOTIONAL_CAVEAT}\n")
    print(f"Total Runs Recorded:     {total_runs}")
    print(f"Completed Runs:          {completed_runs}")
    print(f"Total Notional Cost:     ${total_notional_cost:.4f}")
    print(f"Average Cost / Run:      ${avg_cost_per_run:.4f}")
    print(f"Average Tools / Run:     {avg_tools_per_run:.1f}")
    print(f"Total Tool Errors:       {total_tool_errors}")
    print(f"Overall Tool Reliability: {overall_tool_success_rate * 100:.1f}%\n")

    print("--- TOOL PERFORMANCE SUMMARY ---")
    print(
        f"{'Tool':<20} | {'Calls':<6} | {'OK':<6} | {'Errors':<6} | {'Success Rate':<12} | {'Avg Latency'}"
    )
    print("-" * 70)
    for tool_name, m in sorted(tool_stats.items()):
        print(
            f"{tool_name:<20} | {m.calls:<6} | {m.ok:<6} | {m.errors:<6} | {m.success_rate * 100:>10.1f}% | {m.avg_duration_ms:>6.1f}ms"
        )
    print("-" * 70)

    print("\n--- RECENT RUNS ---")
    print(f"{'Run ID':<20} | {'Status':<18} | {'Tools':<5} | {'Cost (USD)':<10} | {'Product'}")
    print("-" * 70)
    for r in runs[:10]:
        print(
            f"{r.run_id:<20} | {r.status:<18} | {r.tool_calls_used:<5} | ${r.cost_usd:<9.4f} | {r.product.name[:25]}"
        )
    print("-" * 70)

    # 2. Write Markdown report to output_file
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md_lines = [
        "# Campaign Agent Cost & Performance Report",
        "",
        "> [!NOTE]",
        f"> **Notional Cost Caveat**: {NOTIONAL_CAVEAT}",
        "",
        "## Executive Summary",
        "",
        f"- **Total Recorded Runs**: {total_runs}",
        f"- **Completed Runs**: {completed_runs}",
        f"- **Total Notional Spend**: ${total_notional_cost:.4f}",
        f"- **Average Spend / Run**: ${avg_cost_per_run:.4f} (Ceiling: $0.25)",
        f"- **Average Tool Calls / Run**: {avg_tools_per_run:.1f} (Ceiling: 15)",
        f"- **Overall Tool Success Rate**: {overall_tool_success_rate * 100:.1f}%",
        "",
        "## Tool Performance Breakdown",
        "",
        "| Tool Name | Invocations | Successes | Failures | Reliability | Mean Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for tool_name, m in sorted(tool_stats.items()):
        md_lines.append(
            f"| `{tool_name}` | {m.calls} | {m.ok} | {m.errors} | {m.success_rate * 100:.1f}% | {m.avg_duration_ms:.1f} ms |"
        )

    md_lines.extend(
        [
            "",
            "## Recent Campaign Executions",
            "",
            "| Run Identifier | Status | Tool Calls | Notional Cost (USD) | Product Name | Target Segment |",
            "| :--- | :--- | :---: | :---: | :--- | :--- |",
        ]
    )

    for r in runs[:15]:
        md_lines.append(
            f"| `{r.run_id}` | `{r.status}` | {r.tool_calls_used}/15 | ${r.cost_usd:.4f} | {r.product.name} | `{r.product.segment}` |"
        )

    md_lines.append("")
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nReport successfully generated at: {out_path}")
    return 0


def main() -> int:
    out_file = sys.argv[1] if len(sys.argv) > 1 else "docs/cost_report.md"
    return generate_cost_report(out_file)


if __name__ == "__main__":
    sys.exit(main())
