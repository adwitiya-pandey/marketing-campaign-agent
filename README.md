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

## Where LangChain is used

| Concept | File and Function / Class | Exact Import | Purpose |
| :--- | :--- | :--- | :--- |
| **Agent Factory** | `src/campaign/agent.py`<br>`build_agent` | `from langchain.agents import create_agent` | Wraps LangChain 1.4 `create_agent` with model, tools, system prompt, and middleware. |
| **Middleware (Limits)** | `src/campaign/agent.py`<br>`run_phase1`, `run_phase2` | `from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware` | Caps tool calls (15 max across run) and bounds model iteration steps. |
| **Middleware (Hooks)** | `src/campaign/middleware.py`<br>`CostCeilingMiddleware`, `TraceMiddleware` | `from langchain.agents.middleware import AgentMiddleware`<br>`from langchain_core.messages import AIMessage` | Subclasses `after_model` to enforce $0.25 cost ceiling and log JSONL traces. |
| **Tools** | `src/campaign/tools/web_search.py` (`web_search`)<br>`src/campaign/tools/sql_query.py` (`sql_query`)<br>`src/campaign/tools/analytics_lookup.py` (`analytics_lookup`)<br>`src/campaign/tools/draft_copy.py` (`draft_copy`) | `from langchain_core.tools import tool` | Binds safe execution functions to Pydantic argument schemas (`args_schema`). |
| **Chat Model (Live)** | `src/campaign/llm.py`<br>`get_chat_model` | `from langchain_google_genai import ChatGoogleGenerativeAI` | Configures Google Gemini 3.8 Flash with temperature=0, retries, and output token caps. |
| **Chat Model (Offline / Test)** | `src/campaign/llm.py` (`FakeToolModel`)<br>`src/campaign/scripted.py` (`ScriptedChatModel`) | `from langchain_core.language_models.fake_chat_models import GenericFakeChatModel`<br>`from langchain_core.language_models.chat_models import BaseChatModel` | Provides deterministic offline testing and scripted demo chat models with tool binding. |
| **Messages** | `src/campaign/agent.py`<br>`run_phase1`, `run_phase2` | `from langchain_core.messages import HumanMessage` | Formats input user prompts passed to `agent.invoke({"messages": [...]})`. |
| **Tracing** | `src/campaign/tracing.py`<br>`validate_tracing_settings`, `get_invoke_config` | Native LangChain env vars & `RunnableConfig` dict (`tags`, `metadata`, `run_name`) | Configures LangSmith tracing environment and attaches metadata to agent invocations. |

---

## What the Tests Prove and Do Not

> All tests offline, no key, no network. Fake model: `FakeToolModel(GenericFakeChatModel)` with `bind_tools` returning `self` (verified pattern in `docs/sdk_notes.md`), fed an iterator of `AIMessage` objects with `tool_calls` and `usage_metadata`. The **scripted demo model** in `scripted.py` builds, for the three demo products, the exact tool-call sequence and the final JSON; it proves wiring, schemas, bounds, gate, logging; it does **not** prove that Gemini picks good tools or writes good copy. T14 (live) covers that.

---

## Quickstart

Copy and paste the following commands to clone and run the application completely offline:

### Prerequisites
- Python 3.13 (`>=3.13,<3.14`). *Note: `uv` fetches and provisions Python 3.13 automatically if not already present on your machine.*
- `uv` package manager:
  - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - **Windows (PowerShell)**: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Setup and Offline Execution

Run the setup and execution steps below. Pinned dependencies and database seeds ensure 100% offline reproducibility:

#### 1. Clone repository
**Bash:**
```bash
git clone https://github.com/adwitiya-pandey/marketing-campaign-agent.git
cd marketing-campaign-agent
```
**PowerShell:**
```powershell
git clone https://github.com/adwitiya-pandey/marketing-campaign-agent.git
cd marketing-campaign-agent
```

#### 2. Install dependencies with pinned lockfile
**Bash & PowerShell:**
```bash
uv sync
```
*Expected output:*
```text
Resolved 89 packages in 13ms
Checked 83 packages in 13ms
```
*(Note: `uv` fetches and provisions Python 3.13 automatically if not already present).*

#### 3. Create environment file from template
**Bash:**
```bash
cp .env.example .env
```
**PowerShell:**
```powershell
Copy-Item .env.example .env
```

#### 4. Build synthetic customer database (seed 42, 2,000 customers)
**Bash & PowerShell:**
```bash
uv run python scripts/build_db.py
```
*Expected output:*
```text
Database built successfully at data/customers.db with seed 42
```

#### 5. Run end-to-end command line demo (scripted mode, no API key required)
**Bash & PowerShell:**
```bash
uv run python scripts/demo_run.py
```
*Expected output (trimmed):*
```text
======================================================================
STARTING CAMPAIGN RUN (SCRIPTED DEMO)
Product: Brightside Smart Water Bottle
Segment: young-professionals
Budget:  $5000.00
======================================================================
2026-10-27 13:26:27 [info     ] phase1_completed               cost_usd=0.007200000000000001 run_id=RUN-20261027-3528 status=AWAITING_APPROVAL tool_calls_used=3

Phase 1 Complete!
Run ID:          RUN-20261027-3528
Status:          AWAITING_APPROVAL
Tool calls used: 3/15
Notional cost:   $0.0072 (Notional: tokens x pricing; free tier bills $0.00)

--- 5 PROPOSED CAMPAIGN ANGLES ---

[0] Smart Hydration for Busy Professionals
    Positioning: The intelligent hydration system designed specifically for desk-bound professionals and daily commuters.
    Key Message: Build healthy hydration habits automatically without interrupting your workday.
    Reach:       54,000
    Evidence:    Search shows top competitor lacks insulated lid, 68% of customers prefer 24oz capacity
...
Manager Approval: Approving Angle [0]...
2026-10-27 13:26:28 [info     ] phase2_completed               cost_usd=0.0144 run_id=RUN-20261027-3528 status=COMPLETED tool_calls_used=6

Phase 2 Complete!
Status:                COMPLETED
Total tool calls used: 6/15
Total notional cost:   $0.0144 (Notional: tokens x pricing; free tier bills $0.00)

======================================================================
GENERATED CAMPAIGN PACKAGE: 'Smart Hydration for Busy Professionals'
======================================================================

[Google Ads]
Headlines:    Brightside Smart Bottle | Hydrate on Busy Days | Chilled for 24 Hours
Descriptions: Track daily hydration with smart glow reminders. Stainless steel vacuum insulation. // Sleek desk-friendly design with whisper-quiet notifications. Shop Brightside Goods.

[Instagram]
Caption:      Workdays get busy, but staying hydrated should be effortless. The Brightside Smart Bottle reminds you when it's time to drink, keeping your water chilled for 24 hours without plastic. #hydrate #productivity #wellness #brightside #workday
...
Demo run completed successfully.
```

#### 6. Launch Streamlit Human-in-the-Loop dashboard
**Bash & PowerShell:**
```bash
uv run streamlit run src/campaign/app.py
```
*Expected output (trimmed):*
```text
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://172.17.12.43:8501
```

### SCRIPTED DEMO vs. Live Gemini: What is Deterministic vs. Model Answer

This repository supports two execution modes via `LLM_MODE`:

| Execution Aspect | Scripted Demo Mode (`LLM_MODE="scripted"`, Default) | Live Gemini Mode (`LLM_MODE="gemini"`) |
| :--- | :--- | :--- |
| **Model Implementation** | `ScriptedChatModel` (`src/campaign/scripted.py`) subclassing LangChain `BaseChatModel`. | `ChatGoogleGenerativeAI` (`src/campaign/llm.py`) connecting to `gemini-3.8-flash`. |
| **Angle Generation & Copywriting** | **Deterministic fixture**: The 5 proposed angles and 3-channel advertising copy are pre-composed fixtures for 3 demo products. They are **not** an LLM output. | **Dynamic LLM generation**: Google Gemini 3.8 Flash autonomously synthesizes new angles and drafts ad copy from tool outputs. |
| **Tool Invocations** | **Canned call schedule, real execution**: `ScriptedChatModel` emits predefined tool call signatures (`web_search` -> `sql_query` -> `analytics_lookup`), but the tools run **real code**: SQL runs against `customers.db`, reach is computed by `analytics.py`, and search queries local fixtures. | **Dynamic tool calling**: Gemini decides autonomously which tools to call, inspects returned observation outputs, and requests additional data as needed. |
| **Token Usage & Costs** | **Deterministic simulated usage**: Each turn reports fixed token counts (`450 input / 150 output`) to exercise the `CostCeilingMiddleware` and cost accumulation tracking. | **Live API token usage**: Real token counts reported by the Gemini API metadata are accumulated and checked against the $0.25 ceiling. |
| **API Keys & Network** | **100% Offline**: Requires no external network calls, no API keys, and incurs $0.00 notional cost. | **Requires API Key**: Requires `GEMINI_API_KEY` with outbound internet access. |
| **Security & Middleware** | **Identical**: Tool-call cap (15), cost ceiling ($0.25), SQL AST validator, read-only DB boundary, rate limiter, and approval gate apply identically in both modes. | **Identical**: Tool-call cap (15), cost ceiling ($0.25), SQL AST validator, read-only DB boundary, rate limiter, and approval gate apply identically in both modes. |

In the dashboard:
1. Verify the sidebar indicates `SCRIPTED DEMO: outputs are deterministic, not Gemini`.
2. Click **Generate angles** to execute Phase 1 market research.
3. Review the 5 candidate angles, select one, and click **Approve and draft package** (or **Reject**).
4. Inspect the generated Google Ads, Instagram, and Email copy tabs with real-time character counters.
5. Open the **Run Trace & Observability Telemetry** expander to inspect the full execution trace.

---

## Live Gemini Execution

To run against the live Google Gemini API:

**Bash (Linux / macOS / WSL2):**
```bash
# Provide GEMINI_API_KEY as an environment variable or inside .env
export GEMINI_API_KEY="your-gemini-api-key"
export LLM_MODE="gemini"

# Run end-to-end demo using Gemini 3.8 Flash
uv run python scripts/demo_run.py

# Or launch dashboard in live Gemini mode
uv run streamlit run src/campaign/app.py
```

**PowerShell (Windows):**
```powershell
# Provide GEMINI_API_KEY as an environment variable or inside .env
$env:GEMINI_API_KEY="your-gemini-api-key"
$env:LLM_MODE="gemini"

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

## Guardrails and logging at a glance

| Control | Enforcing File | Mechanism & Verification | Real Audit / Trace Log Sample (Secrets & Product Text Excluded) |
| :--- | :--- | :--- | :--- |
| **Tool-call cap 15** | `src/campaign/agent.py` | `ToolCallLimitMiddleware(run_limit=remaining, exit_behavior="end")` halts execution after 15 calls across phases; status becomes `LIMIT_REACHED`. | `{"type":"model_step","ts":"2026-10-27T13:22:59.429259+00:00","run_id":"RUN-20261027-4438","step":4,"tool_calls_requested":0,"input_tokens":450,"output_tokens":150,"running_cost_usd":0.0054,"content_sha256":"34484f6e5f5f86eb03c8bd8c36df5180b16a16827dc078a4b68b27dcfa2bd660"}` |
| **Cost ceiling $0.25** | `src/campaign/middleware.py`<br>`src/campaign/cost.py` | `CostCeilingMiddleware` checks `is_exceeded()` in `after_model`, raising `BudgetExceeded` if notional token spend reaches $0.25. | `{"type":"model_step","ts":"2026-10-27T13:22:59.370976+00:00","run_id":"RUN-20261027-4438","step":2,"tool_calls_requested":1,"input_tokens":450,"output_tokens":150,"running_cost_usd":0.0018,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}` |
| **SQL validator** | `src/campaign/sqlsafe.py` | 7-rule AST validator blocks non-SELECT, multiple statements, comments, and unlisted tables; caps `LIMIT 50`. | `{"ts":"2026-10-27T13:22:26.329366+00:00","run_id":"RUN-20261027-9550","accepted":false,"code":"STACKED_STATEMENTS","sql":"SELECT * FROM customers; DROP TABLE customers","row_count":0}` |
| **Read-only DB** | `src/campaign/db.py` | 3-layer boundary: `mode=ro` URI, `PRAGMA query_only=ON`, and SQLite bytecode authorizer callback. | `{"ts":"2026-10-27T13:22:59.395540+00:00","run_id":"RUN-20261027-4438","accepted":true,"code":null,"sql":"SELECT age_band, AVG(lifetime_value) AS avg_ltv FROM customers GROUP BY age_band LIMIT 50","row_count":5}` |
| **Sanitizer** | `src/campaign/sanitize.py` | Strips control/zero-width characters; flags prompt injections; fails closed on hostile briefs before model invocation. | `{"type":"tool_call","ts":"2026-10-27T13:22:59.419084+00:00","run_id":"RUN-20261027-4438","step":3,"tool":"analytics_lookup","args":"{\"segment\":\"fitness-enthusiasts\",\"channel\":\"instagram\",\"budget_usd\":5000.0}","ok":true,"error_code":null,"result_bytes":49,"duration_ms":4.18}` |
| **Untrusted-data markers** | `src/campaign/sanitize.py`<br>`src/campaign/tools/` | Escapes nested tags and wraps external search snippets and DB records in `<untrusted>` tags to prevent indirect prompt injection. | `{"type":"tool_call","ts":"2026-10-27T13:22:59.396615+00:00","run_id":"RUN-20261027-4438","step":2,"tool":"sql_query","args":"{\"query\":\"SELECT age_band, AVG(lifetime_value) AS avg_ltv FROM customers GROUP BY age_band LIMIT 50\"}","ok":true,"error_code":null,"result_bytes":205,"duration_ms":17.69}` |
| **Rate limit** | `src/campaign/ratelimit.py`<br>`src/campaign/store.py` | Sliding-window limiter backed by SQLite `rate_events` enforces max 10 runs per 600 seconds per user ID. | `{"type":"model_step","ts":"2026-10-27T13:22:59.349763+00:00","run_id":"RUN-20261027-4438","step":1,"tool_calls_requested":1,"input_tokens":450,"output_tokens":150,"running_cost_usd":0.0,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}` |
| **Approval gate** | `src/campaign/service.py` | Phase 2 drafting requires stored `AWAITING_APPROVAL` status and retrieves the angle by index from `runs.db`, ignoring UI payloads. | `{"type":"model_step","ts":"2026-10-27T13:22:59.514369+00:00","run_id":"RUN-20261027-4438","step":1,"tool_calls_requested":1,"input_tokens":450,"output_tokens":150,"running_cost_usd":0.0072,"content_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}` |

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
