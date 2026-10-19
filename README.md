# Marketing Campaign Agent

[![CI](https://github.com/adwitiya-pandey/marketing-campaign-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/adwitiya-pandey/marketing-campaign-agent/actions/workflows/ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> An autonomous tool-using LangChain agent that researches market angles, gates on human approval in a Streamlit dashboard, and drafts multi-channel advertising copy under strict tool and budget ceilings.

---

## Architecture Diagram

```
                      Streamlit dashboard (app.py)
                 user id · product form · 5 angle cards · approve/reject · package · cost · trace
                                   │ service.py (the only orchestrator)
        ┌──────────────────────────┼──────────────────────────────┐
        ▼                          ▼                              ▼
  ratelimit.py              store.py (runs.db)             trace_log.py (JSONL)
  sanitize.py               run state machine              every tool call + model step
        │
        ▼ PHASE 1                                           PHASE 2 (only after approve_angle)
  create_agent(model, tools, middleware)                     create_agent(model, tools, middleware)
    middleware: ToolCallLimit(15 − used) · ModelCallLimit · CostCeiling(0.25 − spent) · Trace
    tools: web_search  sql_query  analytics_lookup           tools: draft_copy  analytics_lookup
        │                                                          │
        ▼                                                          ▼
  final message ─► CampaignAngles (Pydantic, exactly 5)      final message ─► CampaignPackage (Pydantic)

 tools ──► search_backends (fixture | ddgs)   sqlsafe.py ─► db.py (customers.db, mode=ro + query_only + authorizer)
 every SQL string ──► audit/sql_audit.jsonl (accepted or rejected, reason, no row data)
 LangSmith: automatic LangChain tracing when LANGSMITH_TRACING=true
```

---

## What the Tests Prove and Do Not

> All tests offline, no key, no network. Fake model: `FakeToolModel(GenericFakeChatModel)` with `bind_tools` returning `self` (verified pattern in `docs/sdk_notes.md`), fed an iterator of `AIMessage` objects with `tool_calls` and `usage_metadata`. The **scripted demo model** in `scripted.py` builds, for the three demo products, the exact tool-call sequence and the final JSON; it proves wiring, schemas, bounds, gate, logging; it does **not** prove that Gemini picks good tools or writes good copy. T14 (live) covers that.

---

## Quickstart

Copy and paste the following commands to clone and run the application completely offline:

### Prerequisites
- Python 3.13 (`>=3.13,<3.14`)
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Setup and Offline Execution
```bash
# 1. Clone repository
git clone https://github.com/adwitiya-pandey/marketing-campaign-agent.git
cd marketing-campaign-agent

# 2. Install dependencies with pinned lockfile
uv sync

# 3. Create environment file from template
cp .env.example .env

# 4. Build synthetic customer database (seed 42, 2,000 customers)
uv run python scripts/build_db.py

# 5. Run end-to-end command line demo (scripted mode, no API key required)
uv run python scripts/demo_run.py

# 6. Launch Streamlit Human-in-the-Loop dashboard
uv run streamlit run src/campaign/app.py
```

In the dashboard:
1. Verify the sidebar indicates `SCRIPTED DEMO: outputs are deterministic, not Gemini`.
2. Click **Generate angles** to execute Phase 1 market research.
3. Review the 5 candidate angles, select one, and click **Approve and draft package** (or **Reject**).
4. Inspect the generated Google Ads, Instagram, and Email copy tabs with real-time character counters.
5. Open the **Run Trace & Observability Telemetry** expander to inspect the full execution trace.

---

## Live Gemini Execution

To run against the live Google Gemini API:

```bash
# Provide GEMINI_API_KEY as an environment variable or inside .env
export GEMINI_API_KEY="your-gemini-api-key"
export LLM_MODE="gemini"

# Run end-to-end demo using Gemini 3.8 Flash
uv run python scripts/demo_run.py

# Or launch dashboard in live Gemini mode
uv run streamlit run src/campaign/app.py
```

*Note: LangSmith tracing is optional and remains disabled by default (`LANGSMITH_TRACING=false`). All traces and telemetry are saved locally to `logs/agent_trace.jsonl`.*

---

## Enforced Bounds & Controls

Both execution phases share a single resource budget:
- **15 Tool Invocations Limit**: Managed by `ToolCallLimitMiddleware(run_limit=remaining, exit_behavior="end")`. The 16th call is blocked, leaving executed calls at exactly 15 and transitioning the run status to `LIMIT_REACHED`.
- **$0.25 Cost Ceiling**: Tracked per token via `CostCeilingMiddleware`. When accumulated notional spend exceeds $0.25, `BudgetExceeded` is raised from `after_model`, immediately halting execution and updating status to `BUDGET_EXCEEDED` without losing partial state.
- **Maximum 50 SQL Rows**: Enforced by AST analysis in `src/campaign/sqlsafe.py`, automatically rewriting or appending `LIMIT 50`.

---

## Security Architecture Summary

| ID | Control / Requirement | Implementation |
| :--- | :--- | :--- |
| **S1** | Strict 7-Rule SQL Validator | `src/campaign/sqlsafe.py` AST/regex validation with 44 hostile attack tests. |
| **S2** | Read-Only SQLite Security Boundary | `src/campaign/db.py`: `mode=ro`, `PRAGMA query_only=ON`, bytecode authorizer callback. |
| **S3** | Fail-Closed Audit Logging | `audit/sql_audit.jsonl` audits every attempt; query aborts if audit write fails. |
| **S4** | Strict Pydantic Tool Schemas | `extra="forbid"`, bounded types, validation error returns JSON error strings. |
| **S5** | Input Sanitisation & Injection Defense | `src/campaign/sanitize.py` removes control chars, fails closed on prompt injection. |
| **S6** | Untrusted Data Boundary | External web and database strings wrapped in `<untrusted>` markers. |
| **S7** | Shared Allowance Middleware | Enforces 15 tool calls and $0.25 cost ceiling across both phases. |
| **S8** | Sliding Window Rate Limiting | `src/campaign/ratelimit.py` sliding window backed by SQLite `rate_events`. |
| **S9** | Secret Protection & Safe Logging | API keys wrapped in `SecretStr`; product text, raw rows, and keys excluded from logs. |
| **S10** | Store-Gated Human Approval | Phase 2 loads approved angle by index from `runs.db`, ignoring UI payloads. |
| **S11** | No Tool Side Effects | AST verified: no file writes or network side effects outside audit and trace logs. |

---

## Cost & Observability Report (Measured in T14)

> [!NOTE]
> **Notional Cost Caveat**: All costs are notional estimates calculated from configured token rates (SPEC section 10: $1.50/1M input tokens, $7.50/1M output tokens). Google Gemini free tier and scripted demo runs bill $0.00. No actual charges were incurred.

- **Total Recorded Runs**: 31
- **Completed Runs**: 22
- **Average Spend / Run**: $0.0123 (Ceiling: $0.25)
- **Average Tool Calls / Run**: 5.1 (Ceiling: 15)
- **Overall Tool Reliability**: 100.0%

### Tool Performance Metrics
| Tool Name | Calls | Successes | Failures | Reliability | Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `analytics_lookup` | 43 | 43 | 0 | 100.0% | 1.7 ms |
| `draft_copy` | 96 | 96 | 0 | 100.0% | 1.7 ms |
| `sql_query` | 43 | 43 | 0 | 100.0% | 5.5 ms |
| `web_search` | 45 | 45 | 0 | 100.0% | 2.7 ms |

Detailed breakdowns are documented in [docs/cost_report.md](docs/cost_report.md) and [docs/trace_summary.md](docs/trace_summary.md).

---

## Known Limitations

Per SPEC section 20:
1. **Synthetic Customer Data**: The SQLite database contains purely synthetic demographic data without real customer PII.
2. **Mock Reach Calculations**: Reach metrics are computed deterministically from segment, channel, and budget formulas.
3. **Fixture Search Default**: Default search queries return fixture records; the live DuckDuckGo backend is optional.
4. **Scripted Demo Execution**: Default mode executes deterministic canned model sequences; it does not exercise Gemini.
5. **No Authentication**: User IDs are typed strings; user authorization is outside the current scope.
6. **Notional Token Costing**: Token pricing is checked after each model step; worst-case overshoot is bounded by `max_output_tokens` (~1.5 cents).
7. **No Evaluator in Loop**: Content validation is restricted to Pydantic schema validation and compliance keyword scanning without LLM-as-judge scoring.

---

## Repository Structure

```
marketing-campaign-agent/
├── src/campaign/
│   ├── agent.py              # Two-phase create_agent execution and repair loop
│   ├── analytics.py          # Deterministic reach estimation
│   ├── app.py                # Streamlit HITL dashboard
│   ├── compliance.py         # Word-boundary banned phrase scanner
│   ├── config.py             # Pydantic-settings configuration
│   ├── cost.py               # Token cost tracker and BudgetExceeded exception
│   ├── db.py                 # 3-layer read-only SQLite database connection
│   ├── llm.py                # Model factory (Gemini, scripted, fake)
│   ├── logging_setup.py      # Structlog JSON logger with sensitive data filtering
│   ├── middleware.py         # Tool limit, cost ceiling, and trace middleware
│   ├── models.py             # Pydantic v2 schemas and strict regex validators
│   ├── prompts.py            # Phase 1, Phase 2, and repair prompt templates
│   ├── ratelimit.py          # SQLite sliding-window rate limiter
│   ├── sanitize.py           # Control char stripper and prompt injection detector
│   ├── scripted.py           # Deterministic offline demo chat model
│   ├── search_backends.py    # FixtureSearch and lazy DdgsSearch backends
│   ├── service.py            # Service orchestrator and human approval gate
│   ├── sqlsafe.py            # 7-rule AST SQL security validator
│   ├── store.py              # Run state machine and SQLite persistence
│   ├── trace_log.py          # Local append-only JSONL trace writer
│   ├── tracing.py            # LangSmith configuration and invoke metadata
│   └── tools/                # Pydantic-typed tools (search, sql, reach, copy)
├── scripts/
│   ├── build_db.py           # Customer database generator (seed 42, 2,000 rows)
│   ├── cost_report.py        # Cost and tool performance report generator
│   ├── demo_run.py           # End-to-end scripted campaign run
│   ├── explain_run.py        # Run explanation and trace join utility
│   └── live_demo_run.py      # Live Gemini execution runner
├── tests/                    # 193 offline unit, agent, service, and AppTest tests
├── docs/                     # Architecture, threat model, decisions, cost reports
├── pyproject.toml            # Project dependencies and tool configurations
└── README.md
```

---

## License

This project is licensed under the terms of the [MIT License](LICENSE).
Adwitiya Pandey &copy; 2026.
