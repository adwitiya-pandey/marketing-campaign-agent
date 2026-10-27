# Campaign Agent Cost & Performance Report

> [!NOTE]
> **Notional Cost Caveat**: All costs listed in this report are notional estimates calculated from configured token rates (SPEC section 10: $1.50/1M input tokens, $7.50/1M output tokens). Google Gemini free tier and scripted demo runs bill $0.00. No actual charges were incurred.
>
> **Historical Benchmark Snapshot (Recorded on 2026-10-19 / T14)**: The metrics and tables below represent an immutable snapshot of 31 runs executed during the T14 benchmark cycle. Because `scripts/cost_report.py` dynamically aggregates all runs stored in `data/runs.db` and `logs/agent_trace.jsonl`, executing `uv run python scripts/cost_report.py` in an active workspace will calculate fresh metrics reflecting all subsequent runs.

## Executive Summary

- **Total Recorded Runs**: 31
- **Completed Runs**: 22
- **Total Notional Spend**: $0.3816
- **Average Spend / Run**: $0.0123 (Ceiling: $0.25)
- **Average Tool Calls / Run**: 5.1 (Ceiling: 15)
- **Overall Tool Success Rate**: 100.0%

## Tool Performance Breakdown

| Tool Name | Invocations | Successes | Failures | Reliability | Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `analytics_lookup` | 43 | 43 | 0 | 100.0% | 1.7 ms |
| `draft_copy` | 96 | 96 | 0 | 100.0% | 1.7 ms |
| `sql_query` | 43 | 43 | 0 | 100.0% | 5.5 ms |
| `web_search` | 45 | 45 | 0 | 100.0% | 2.7 ms |

## Recent Campaign Executions

| Run Identifier | Status | Tool Calls | Notional Cost (USD) | Product Name | Target Segment |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `RUN-20261019-7685` | `COMPLETED` | 6/15 | $0.0144 | EcoBento Reusable Lunch Box | `young-professionals` |
| `RUN-20261019-1263` | `COMPLETED` | 6/15 | $0.0144 | TerraGrip Trail Running Shoes | `fitness-enthusiasts` |
| `RUN-20261019-6287` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-4397` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-5349` | `REJECTED` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-7556` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-2403` | `AWAITING_APPROVAL` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-4445` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-3405` | `REJECTED` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-8287` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-2826` | `AWAITING_APPROVAL` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-9205` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-3172` | `REJECTED` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-6400` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
| `RUN-20261019-6337` | `AWAITING_APPROVAL` | 3/15 | $0.0072 | Brightside Smart Water Bottle | `young-professionals` |
