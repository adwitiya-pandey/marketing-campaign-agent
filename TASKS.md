# TASKS: marketing-campaign-agent

> **AUTONOMOUS END-TO-END EXECUTION RULE (SINGLE-CHAT WORKFLOW)**:
> Execute **all tasks in `TASKS.md` back-to-back from `T0`/`H0` through `v0.1.0` GitHub push** in a single continuous run.
> - **Do NOT stop after individual tasks** to wait for human PR merges. Commit each task cleanly with Conventional Commits (`Refs: <TaskID>`), merge branches automatically, update `PROGRESS.md`, and continue straight to the next task.
> - **Write 100% of the code yourself** (including `queries.py`, `graph.py`, `policy.py`, `approvals.py`, `sqlsafe.py`, and the `H9` merge conflict).
> - **API Keys**: Use `GEMINI_API_KEY` from the project's `.env` file for live Gemini steps. Never require `ANTHROPIC_API_KEY` or `LANGSMITH_API_KEY`.


Order matters. Execute all tasks sequentially from start to finish in a single autonomous run. Owner tags: **AGENT** = coding agent does it; **HUMAN** = the owner does it; **REVIEW** = the owner reads and explains it back.

**Gate before starting:** Projects A and B are tagged `v0.1.0`. This repo is built after the supply-chain repo (order: A, B, supply chain, marketing agent).

| Phase | Tasks |
|---|---|
| Foundations | T0, T1, T2 |
| Data and state | T3, T4 |
| Safe building blocks | T5, T6, T7 (AGENT) |
| Tools and agent | T8, T9, T10 (AGENT) |
| Demo and UI | T11, T12 (AGENT) |
| Observability and evidence | T13, T14, T15 (AGENT) |
| Ship | T16 (AGENT) |

Branch model: `main` plus one branch per task (`task/T9-agent`). The agent commits on each task branch, runs tests, merges into `main` automatically, documents the task in `docs/EXPLAIN-PLAIN-ENGLISH.md`, and continues to the next task without stopping. Two-step git always: `git branch <name>`, then `git switch <name>`.

Commit style: Conventional Commits with a `Refs: T9` trailer (see AGENTS.md).

---

## T0 (AGENT): create public GitHub repository `adwitiya-pandey/marketing-campaign-agent`
Work in WSL2 Ubuntu under `~/projects`. `gh auth status` must show the account `adwitiya-pandey`.
1. `mkdir -p ~/projects/marketing-campaign-agent && cd ~/projects/marketing-campaign-agent`. Copy in this pack's files (`AGENTS.md`, `SPEC.md`, `TASKS.md`, `.gitignore`, `.gitattributes`, `.editorconfig`, `.vscode/`, `.github/agents/`, `docs/`). `PLAN-PRIVATE.md` stays on your disk (gitignored). Then `find . -name '*Zone.Identifier' -delete`.
2. One command at a time: `git init`, `git branch -M main`, `git add .`, `git status` (no Zone.Identifier, no PLAN-PRIVATE.md), `git commit -m "docs: add scope contract (AGENTS, SPEC, TASKS)"`.
3. `gh repo create adwitiya-pandey/marketing-campaign-agent --public --source=. --remote=origin --push --description "LangChain marketing agent: web search, read-only SQL, analytics, human-approved campaign angles, 15-call and 25-cent bounds"`. Open the URL in a private window.
4. In VS Code (WSL window) choose the `builder` agent, confirm the model shown is Gemini 3.8 Flash High (Antigravity) / Copilot Auto, and ask: "List the instruction files you loaded in this chat and quote the first line of each." `AGENTS.md` must be listed.
5. Read SPEC sections 1 to 11 once. Write nothing.
6. **Resume check:** the resume lists this project without a link. Add `github.com/adwitiya-pandey/marketing-campaign-agent` after T16. Until then say "in progress" if asked.
Accept: GitHub shows the pack files; the instruction-file check passes.

## T1 (AGENT): scaffold, CI, settings, SDK facts
Branch: `git branch task/T1-scaffold` then `git switch task/T1-scaffold`.
1. `uv init --package --python 3.13`; layout from SPEC 17 with empty modules, each with a one-line docstring. Dependencies exactly as SPEC 17 (pinned; extra `live-search`).
2. `.env.example` with every variable in SPEC 16 and dummy values; `LICENSE` (MIT, holder Adwitiya Pandey); minimal `README.md` saying "Status: in progress".
3. `.github/workflows/ci.yml` per SPEC 17. Look up current action versions; do not guess.
4. `docs/sdk_notes.md` is pre-filled. In a scratch script (not committed), re-run its probe against the versions `uv` installs and correct the file where anything differs.
5. `tests/conftest.py` sets `LANGSMITH_TRACING=false` before imports. One smoke test imports the package and `langchain.agents.create_agent`.
Accept: `uv sync` then `uv run ruff check . && uv run pytest -q` pass; `docs/sdk_notes.md` is re-verified.

## T2 (AGENT): models, config, logging, trace log
1. `models.py` per SPEC 6. `config.py` per SPEC 16 (`SecretStr`, validation, never echo secrets). `logging_setup.py` (structlog JSON, contextvars, allowed fields only). `trace_log.py` (append-only JSONL writer, SPEC 12: model-step and tool-call records, args truncated, no payloads, `sha256` helper).
2. Tests: every model with valid, extra field, wrong type, bounds, distinct-title rule, exactly-5 rule, ID patterns (trailing newline, non-ASCII digits); config; log capture proves no product text or key can be logged; trace log fields.
Accept: `uv run pytest tests/test_models.py tests/test_config.py tests/test_logging.py tests/test_trace_log.py -q`.
REVIEW: explain why `extra="forbid"` matters for tool arguments and model output.

## T3 (AGENT): customer database, fixtures, read-only access, SQL audit
1. `scripts/build_db.py` (SPEC 5 schema; seed 42; 2 000 customers; no direct identifiers; purchases). `data/fixtures/search.json` (three demo products, at least 6 results each, one injected-instruction snippet per product). `db.py` with the three read-only layers, step limit, one connection per call. `audit` writer for `sql_audit.jsonl` (append-only, fail-closed, JSON-escaped, 500 character cap).
2. Tests: DB builds deterministically (same seed, same checksum); CHECK constraints; INSERT, UPDATE, DELETE, DROP, ATTACH and `PRAGMA` writes fail through `db.py` (S2); runaway query aborted by the step limit; audit line fields and no row data; audit failure raises.
Accept: `uv run pytest tests/test_db.py tests/test_sql_audit.py -q`; `uv run python scripts/build_db.py --out data/customers.db` succeeds.
REVIEW: explain `mode=ro`, `query_only` and the authorizer, and what each stops.

## T4 (AGENT): run store and state machine
1. `store.py`: `runs.db` schema (`runs`, `rate_events`), `RunRecord` persistence, transitions per SPEC 7 (only valid transitions; invalid raises `InvalidTransition`), parameterised SQL.
2. Tests: every valid and invalid transition; JSON round trip of angles and package; restart (close and reopen the connection) keeps state; SQL injection in `user_id` is impossible (pattern plus parameters).
Accept: `uv run pytest tests/test_store.py -q`.

## T5 (AGENT): sanitising, compliance, analytics (tests first)
1. `tests/test_sanitize.py` (control and format characters, length cap, markers, at least 12 injection positives and 8 negatives, flagged versus rejected for the brief), `tests/test_compliance.py` (every banned phrase, boundaries, the `% off` rule), `tests/test_analytics.py` (hand-computed reach for at least 6 inputs, monotonic in budget, bounds). Watch them fail.
2. Implement `sanitize.py`, `compliance.py`, `analytics.py` (choose and document the constants).
Accept: `uv run pytest tests/test_sanitize.py tests/test_compliance.py tests/test_analytics.py -q`.
REVIEW: explain why a flagged brief is rejected but a flagged web result is only wrapped.

## T6 (AGENT): SQL hostile cases, stub, rate limiter
1. `tests/test_sqlsafe.py` from SPEC 9: **at least 25 hostile cases** (stacked statements, `;` inside strings, `--` and `/* */` comments, case and whitespace tricks, tabs and newlines, Unicode lookalikes and zero-width characters, `WITH`, subqueries on `sqlite_master`, `pragma_` table functions, `load_extension`, `ATTACH`, `INSERT ... SELECT`, `SELECT ... INTO`, a table outside the allowlist, a join to one, `LIMIT` tricks, empty, overlong) and at least 10 benign ones (joins, GROUP BY, aggregates, ORDER BY, LIMIT rewrite). One extra test bypasses `validate` and proves the connection still refuses writes (S2).
2. `sqlsafe.py`: only the `validate` signature, `SqlRejected`, `ValidatedSql`, docstrings and `raise NotImplementedError`.
3. `tests/test_ratelimit.py` and `ratelimit.py` (SPEC 13, injected clock, persistence through `store.py`): implement fully.
Accept: the new SQL tests fail only because of `NotImplementedError`; `uv run pytest tests/test_ratelimit.py -q` passes.

## T7 (AGENT): implement SELECT-only SQL validator (`sqlsafe.py`)
Implement `sqlsafe.validate` in `src/campaign/sqlsafe.py` enforcing all 7 rules from SPEC 9 until all 25+ hostile and 10+ benign test cases in `tests/test_sqlsafe.py` pass, and document all 7 rules in `docs/EXPLAIN-PLAIN-ENGLISH.md`.
Accept: `uv run pytest tests/test_sqlsafe.py -q` passes and `ruff` is clean.

## T8 (AGENT): tools and search backends
1. `search_backends.py` (`FixtureSearch`; optional `DdgsSearch` behind the `live-search` extra, imported lazily, never used in tests), `tools/web_search.py`, `tools/sql_query.py`, `tools/analytics_lookup.py`, `tools/draft_copy.py` per SPEC 8, each with a Pydantic `args_schema`, returning JSON strings, `sql_query` calling `sqlsafe.validate` then `db.py` and always auditing.
2. Tests with mocked backends: valid and invalid arguments (invalid returns an error string, never raises into the agent); fixture injection snippet wrapped and flagged; SQL rejection returns `REJECTED: <code>`; rows capped at 50; success and error counters; `tests/test_boundaries.py` (AST: no write calls in `tools/`, tool name list snapshot, no import of `service` from `agent.py` or `tools/`, no `langchain_classic`, no `AgentExecutor` anywhere in `src/`).
Accept: `uv run pytest tests/test_tools.py tests/test_boundaries.py -q`.

## T9 (AGENT): cost, middleware, LLM factory, agent (tests first)
1. `tests/test_cost.py` and `tests/test_agent.py` first, with `FakeToolModel` (pattern in `docs/sdk_notes.md`): phase 1 happy path (three tools, final JSON, five angles); phase 2 happy path (`draft_copy` for three channels, package validated); invalid JSON then valid (repair); repair exhausted (`FAILED`); tool limit reached (model asks for 20 calls, exactly 15 executed, status `LIMIT_REACHED`); cost ceiling exceeded (usage metadata large, `BUDGET_EXCEEDED`, partial state kept); tool called with invalid arguments; SQL rejected then corrected. Watch them fail.
2. `cost.py` (`CostTracker`, `BudgetExceeded`), `middleware.py` (`CostCeilingMiddleware`, `TraceMiddleware`), `prompts.py`, `llm.py` (Gemini branch; scripted branch imports `scripted.py` lazily), `agent.py` (`build_agent`, `run_phase1`, `run_phase2` returning a typed result with `status`, `tool_calls_used`, `cost_usd`; specific exception handling; shared allowance).
Accept: `uv run pytest tests/test_cost.py tests/test_agent.py -q`.
REVIEW: explain what happens at call 16 and at the cost ceiling, and the worst-case overshoot.

## T10 (AGENT): service and the human gate
1. `service.py` per SPEC 7: `start_run`, `approve_angle`, `reject_run`, rate limiting, sanitising, phase calls, store updates, audit and trace lines, structlog contextvars (`run_id`, `phase`).
2. Tests with the fake model: full flow to `COMPLETED`; reject; double approve; approve from a wrong status; index out of range; angle taken from the store not the payload (S10); rate limited; phase 2 with zero allowance makes no model call; hostile brief rejected.
Accept: `uv run pytest tests/test_service.py -q`.
REVIEW: draw the state machine and say what each transition checks.

## T11 (AGENT): scripted demo model, demo script, reports
1. `scripted.py`: a fake chat model that, for each of the three demo products, emits the real tool-call sequence (so the real tools run) and the final JSON (5 angles; then the package), with plausible usage metadata. Document in its docstring that it is a deterministic demo, not an LLM.
2. `scripts/demo_run.py` (full flow in scripted mode, prints the angles and package), `scripts/explain_run.py RUN_ID` (joins stored angles with trace lines), `scripts/cost_report.py` (per-run notional cost, tool success rates, writes `docs/cost_report.md` with the notional-cost caveat).
3. Tests: demo flow for all three products ends `COMPLETED` offline; injection fixture present in search results and the final angles unchanged; `explain_run` output contains each angle title and its tool calls.
Accept: `uv run pytest tests/test_scripted.py tests/test_scripts.py -q`; `uv run python scripts/demo_run.py` exits 0.

## T12 (AGENT): Streamlit dashboard
1. `app.py` (SPEC 2, 12): sidebar with user id and mode banner (scripted: "SCRIPTED DEMO: outputs are deterministic, not Gemini"); product form; "Generate angles"; five angle cards with evidence and estimated reach; select one and "Approve and draft package", or "Reject"; package tabs (Google Ads, Instagram, Email) with character counters; run status, tool calls used out of 15, notional cost out of 0.25, tool success rate; an expander with the run's trace lines; rate-limited and error states with clear messages. Everything from models, tools or the database is rendered as plain text, never as HTML or raw Markdown with HTML.
2. `tests/test_app.py` with `AppTest`: banner; generate shows 5 angles; approve shows the package; reject ends the run; rate limit message; hostile brief rejected.
Accept: `uv run pytest tests/test_app.py -q`; `uv run streamlit run src/campaign/app.py` starts (the owner checks it in a browser).
REVIEW: run it yourself end to end and read the trace expander.

## T13 (AGENT): tracing config and CI hardening
1. `tracing.py`: validates the LangSmith settings, logs whether tracing is on, adds `run_name`, `tags`, `metadata` to the invoke config (no network in tests). Look up the current LangSmith docs for LangChain agents; record the page URL in `docs/sdk_notes.md`.
2. CI: coverage gate 85%, `uv lock --check`.
Accept: `uv run pytest -q --cov=src/campaign --cov-fail-under=85`.

## T14 (AGENT): live Gemini run, local trace report & measured cost
1. Using `GEMINI_API_KEY` from the project's `.env` file (with `LLM_MODE=gemini` and `LANGSMITH_TRACING=false` since no LangSmith key is needed), run the three demo products through the two-phase service.
2. Run `uv run python scripts/cost_report.py` and `uv run python scripts/explain_run.py`, writing `docs/cost_report.md` and `docs/trace_summary.md`.
Accept: `docs/cost_report.md` and `docs/trace_summary.md` committed.

## T15 (AGENT): documentation
1. `README.md`: title, badges, one-line description, architecture diagram (ASCII from SPEC 4), what the tests prove and do not (SPEC 15 wording), quickstart (copy-paste: prerequisites, clone, `uv sync`, `cp .env.example .env`, build DB, demo script, Streamlit, generate, approve), live mode instructions (key as shell variable), bounds and how they are enforced, security summary, cost section (measured numbers from T14 only), limitations (SPEC 20), repo tree, licence.
2. `docs/architecture.md`, `docs/threat_model.md` (assets, trust boundaries, threats mapped to S1 to S11, residual risks), `docs/decisions.md` (SPEC 19, each with a "what would change my mind" line).
3. Re-run the quickstart commands exactly as written in a fresh `git clone` into a temp folder and fix anything that fails.
Accept: the quickstart commands run from a fresh clone; links resolve.

## T16 (AGENT): final verification, git tag `v0.1.0`, and push to GitHub
1. Fresh clone into a temp folder; follow the README exactly; generate and approve in scripted mode.
2. Check the claims table in `PLAN-PRIVATE.md`; every line must be true.
3. `git tag -a v0.1.0 -m "First release"`, `git push origin v0.1.0`; create a GitHub release.
4. Add the repo link to the resume line; send the updated resume only to new recipients.
Accept: CI green on `main`; tag visible; the README works for someone who is not you.
