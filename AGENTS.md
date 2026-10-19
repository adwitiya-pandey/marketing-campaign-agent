# AGENTS.md

> **AUTONOMOUS END-TO-END EXECUTION RULE (SINGLE-CHAT WORKFLOW)**:
> Execute **all tasks in `TASKS.md` back-to-back from `T0`/`H0` through `v0.1.0` GitHub push** in a single continuous run.
> - **Do NOT stop after individual tasks** to wait for human PR merges. Commit each task cleanly with Conventional Commits (`Refs: <TaskID>`), merge branches automatically, update `PROGRESS.md`, and continue straight to the next task.
> - **Write 100% of the code yourself** (including `queries.py`, `graph.py`, `policy.py`, `approvals.py`, `sqlsafe.py`, and the `H9` merge conflict).
> - **API Keys**: Use `GEMINI_API_KEY` from the project's `.env` file for live Gemini steps. Never require `ANTHROPIC_API_KEY` or `LANGSMITH_API_KEY`.


Read SPEC.md (the contract), the TASKS.md task you were given, and the SPEC sections that task cites, before touching code. This file holds only what is not obvious from the code.

## What this is
A LangChain agent for a fictional retailer's marketing team. Phase 1: given a product and an audience segment, the agent researches (web search, read-only SQL over a synthetic customer database, mock analytics) and proposes exactly 5 campaign angles. A manager approves one in a Streamlit dashboard. Phase 2: the agent drafts Google Ads, Instagram and email copy for that angle. Bounded to 15 tool calls and a 25-cent notional cost per run. Python 3.13, `uv`, LangChain 1.4 (`create_agent`), Pydantic v2, Gemini 3.8 Flash (live mode) or a scripted fake model (default, offline).

## Environment and commands
- The owner works in WSL2 Ubuntu (repo under `~/projects`, never under `/mnt/c` or `/mnt/d`) and sometimes opens it from Windows. CI runs Linux. Use `pathlib`; no shell-specific paths. Tests run offline with no API key set and no network. Line endings are LF.
- Install: `uv sync`
- Check: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- Run each task's own acceptance command from TASKS.md before committing.
- Run only the commands above, the task's own commands, and `git`/`gh` for the task's branch and PR. Ask before anything else.

## Gotchas that will bite you
1. **Use `langchain.agents.create_agent`, never `AgentExecutor`.** `AgentExecutor` lives in the legacy `langchain-classic` package; do not install or import it (SPEC V1).
2. **Limits are middleware, not prompts.** `ToolCallLimitMiddleware(run_limit=N, exit_behavior="end")` lets N calls execute and answers the next with a "limit reached" message (verified: `docs/sdk_notes.md`). A custom middleware raises `BudgetExceeded` from `after_model`; the exception propagates out of `invoke` (verified). Both phases share one allowance: `15 - used`, `0.25 - spent`.
3. **The human gate is code between two agent runs** (`service.py`). Phase 2 reads the chosen angle from the stored run by index, only from status `AWAITING_APPROVAL`. Nothing in `agent.py` or `tools/` may call `approve_angle`.
4. **The model's final message is validated by Pydantic in code.** Do not use `response_format` (unverified with Gemini plus tools). One repair attempt, then `FAILED`. Never fabricate or "fix up" model output silently.
5. **SQL: the read-only connection is the security boundary, the regex is a first filter.** `db.py`: `mode=ro`, `PRAGMA query_only=ON`, authorizer (SELECT, READ, FUNCTION only), step limit, one connection per call, parameterised SQL for anything the code itself writes. Every SQL attempt is audited (SQL text, accepted or not, reason code, no row data).
6. **Hostile text is everywhere:** the product brief, web results, database text, model output. Sanitise, wrap in `<untrusted>` markers, never put it in a system prompt, never log product text, SQL result rows or keys.
7. **Do not invent SDK or framework APIs.** `docs/sdk_notes.md` holds what was verified on 17 and 18 Oct 2026 (langchain 1.4.6, langchain-google-genai 4.4.2, langsmith 0.14.11, streamlit 1.66.0, Python 3.13). Re-run its probe against the installed versions before coding against them and correct the file if anything differs. If something is not documented, read the installed package or the official docs, record the finding there, and use the simplest documented pattern.
8. **Regex:** `re.fullmatch` and `[0-9]` for IDs (`\d` matches non-ASCII digits; `$` matches before a trailing newline). Add failing test cases before changing a pattern. Never loosen a pattern to make a test pass.
9. **Cost is notional** (tokens x configured price); the free tier bills zero. Say so wherever a cost is shown. Never publish a cost, latency or success-rate number that was not measured.
10. **No tool has a side effect** beyond the audit and trace logs. No send, publish, or write tools. `draft_copy` validates and normalises; it stores nothing.

## Never
- Implement `src/campaign/sqlsafe.py` completely in T7 after writing the 25+ hostile SQL test cases in T6.
- Keep unit tests (`T1`–`T13`) 100% offline. In `T14`, use `GEMINI_API_KEY` from the project's `.env` file (with `LANGSMITH_TRACING=false` since the owner has no `LANGSMITH_API_KEY`; `trace_log.py` captures all model and tool spans locally into JSONL and `docs/trace_summary.md`) to run a live demo cycle and generate `docs/cost_report.md`.
- Never print or commit `.env` (keep `.env` in `.gitignore`; load it automatically via `python-dotenv` / `pydantic-settings`), real keys, `*.db` files, `audit/` or `logs/`. Create `.env.example` only, with dummy values. The owner stores `GEMINI_API_KEY` in the project's local `.env` file (which is gitignored and loaded via `python-dotenv` / `pydantic-settings`). Never print or commit `.env`. Never enable LangSmith tracing in tests.
- Never add a dependency that is not in SPEC section 17 without asking. No `langchain-classic`, no LangGraph imports of your own, no vector databases, no numpy or pandas.
- Never change SPEC.md, a limit (15 calls, 25 cents, 5 angles, 50 rows), a validator rule or a security requirement to make a test pass. Fix the code, or stop and ask.
- Never skip, delete or weaken a SQL, injection, limit or gate test.
- Never use real personal data. The customer database has no names, emails or other direct identifiers, and must stay that way.

## Work style: autonomous, with a short list of reasons to stop
- One task per branch (`task/T9-agent`), execute all tasks in order continuously, updating PROGRESS.md after each task. Your first message: the task ID, the files you will touch, the tests you will write first, the acceptance command. Keep it short, then proceed.
- Tests first for T5 (sanitize, compliance, analytics), T6 (SQL cases, rate limiter), T9 (agent limits and repair): write the failing tables from the SPEC, watch them fail, then implement.
- Commits follow Conventional Commits: `type(scope): imperative summary`, at most 72 characters, no task ID in the subject. Types: `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`. Put `Refs: T5` as a trailer. Example: `feat(tools): add analytics lookup with deterministic mock reach`.
- Commit with a conventional title (`Refs: T<N>`), merge into `main` automatically, and proceed immediately to the next task. Do not ask permission for routine work.
- Two-step git in any instructions you write for the owner: `git branch <name>` then `git switch <name>`; never `git checkout -b`.
- Facts only from official docs (LangChain, LangSmith, Gemini API, Pydantic, Streamlit, SQLite, pytest, uv) and the installed packages. No blog posts.
- Execute all tasks T0 through T16 continuously, including T7 (`sqlsafe.py`) and T14 (live Gemini run and cost report).
- Model choice (Copilot): Gemini 3.8 Flash High (Antigravity) / Copilot Auto for every task. T9, T10 and T12 are where subtle mistakes hide: re-read your diff against the SPEC before opening the PR.
- Keep replies short: what changed, the last lines of the acceptance command, what the owner should read.

**Stop and ask the owner before:** adding or upgrading a dependency; changing SPEC.md, a limit or a rule; any live model or web call; any network access other than package installs and official docs; deleting or renaming files outside the task's scope; anything that weakens the SQL boundary, the limits, the human gate or the injection defences.

If SPEC is ambiguous, choose the safer reading (stricter validation, less logging), record the question in `docs/open_questions.md`, and continue.

## Definition of done for every task
The acceptance command passes; ruff is clean; new behaviour has a test (written first where listed); `docs/decisions.md` is updated if a decision changed; the code reads clearly to a reviewer (short functions, a comment saying why, no cleverness). End the PR body with three lines: what changed, how it was verified, what the owner should read to understand it.

## Harness
This file is read by VS Code Copilot (setting `chat.useAgentsMdFile`) and by Antigravity (1.20.5 or later). If it is not in your context, say so before doing anything else. Keep this file under 12,000 characters (Antigravity's per-rules-file limit).
