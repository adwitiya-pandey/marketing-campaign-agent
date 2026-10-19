# Campaign Agent Cost & Performance Report

> [!NOTE]
> **Notional Cost Caveat**: All costs listed in this report are notional estimates calculated from configured token rates (SPEC section 10: $1.50/1M input tokens, $7.50/1M output tokens). Google Gemini free tier and scripted demo runs bill $0.00. No actual charges were incurred.

## Executive Summary

- **Total Recorded Runs**: 1
- **Completed Runs**: 1
- **Total Notional Spend**: $0.0144
- **Average Spend / Run**: $0.0144 (Ceiling: $0.25)
- **Average Tool Calls / Run**: 6.0 (Ceiling: 15)
- **Overall Tool Success Rate**: 100.0%

## Tool Performance Breakdown

| Tool Name | Invocations | Successes | Failures | Reliability | Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `analytics_lookup` | 1 | 1 | 0 | 100.0% | 1.5 ms |
| `draft_copy` | 3 | 3 | 0 | 100.0% | 1.8 ms |
| `sql_query` | 1 | 1 | 0 | 100.0% | 11.4 ms |
| `web_search` | 3 | 3 | 0 | 100.0% | 2.3 ms |

## Recent Campaign Executions

| Run Identifier | Status | Tool Calls | Notional Cost (USD) | Product Name | Target Segment |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `RUN-20261019-3646` | `COMPLETED` | 6/15 | $0.0144 | Brightside Smart Water Bottle | `young-professionals` |
