# Marketing Campaign Agent: Plain English Guide

## T0: Repository Initialization and Scope Contract
- Created the public GitHub repository `adwitiya-pandey/marketing-campaign-agent`.
- Tracked initial contract files (`AGENTS.md`, `SPEC.md`, `TASKS.md`, `.editorconfig`, `.gitattributes`, `.gitignore`, `.vscode/`, `.github/agents/builder.agent.md`, and `docs/sdk_notes.md`).
- Cleaned up Windows zone identifiers and ensured `.env` is gitignored.

## T1: Project Scaffold, CI, Environment, and SDK Verification
- Initialized Python 3.13 packaging with `uv` (`requires-python = ">=3.13,<3.14"`).
- Pinned runtime dependencies: `langchain==1.4.6`, `langchain-google-genai==4.4.2`, `langsmith==0.14.11`, `streamlit==1.66.0`, `pydantic-settings==2.16.0`, `structlog==26.1.0`.
- Configured optional extra `live-search = ["ddgs==9.16.0"]` and dev dependencies (`pytest==9.1.1`, `pytest-cov==7.1.0`, `ruff==0.17.1`).
- Created `.env.example` with dummy values for all 20 required configuration settings.
- Added MIT license and minimal status README.
- Configured GitHub Actions workflow (`.github/workflows/ci.yml`) using `actions/checkout@v4`, `astral-sh/setup-uv@v5`, and Python 3.13.
- Re-verified SDK assumptions from `docs/sdk_notes.md` against installed packages using an offline probe script:
  1. `ToolCallLimitMiddleware(run_limit=2, exit_behavior="end")` allows exactly 2 tool calls and terminates on the 3rd.
  2. `CostCeilingMiddleware` raises `BudgetExceeded` from `after_model`, cleanly propagating out of `agent.invoke`.
  3. `ChatGoogleGenerativeAI` constructs offline with dummy credentials.
- Configured `tests/conftest.py` ensuring `LANGSMITH_TRACING=false` before test imports, and validated initial smoke tests.

## T2: Domain Models, Settings Configuration, Structured Logging, and Trace Log
- Implemented strict Pydantic v2 domain models in `src/campaign/models.py` (`extra="forbid"`):
  - `ProductBrief`: strictly bounded inputs (name 2..80, description 10..2000, 4 valid segments, budget $100..$100,000).
  - `CampaignAngle` & `CampaignAngles`: exactly 5 angles with case-insensitive distinct title validation and bounded evidence fields.
  - Channel copy models (`GoogleAdsCopy`, `InstagramCopy`, `EmailCopy`) with character limits, headline/description counts, and strict hashtag regexes (`^#[A-Za-z0-9]{2,30}$`).
  - Strict ASCII regex validation for `run_id` (`^RUN-[0-9]{8}-[0-9]{4}$`) and `user_id` (`^[A-Za-z][A-Za-z0-9_.-]{1,31}$`), strictly rejecting trailing newlines and non-ASCII/Unicode digits.
- Built environment-backed configuration in `src/campaign/config.py` using `pydantic-settings`:
  - `SecretStr` wrappers for API keys, guaranteeing secrets are never echoed in logs, `repr()`, `str()`, or dictionary serializations.
  - Fail-fast validation requiring `GEMINI_API_KEY` when `LLM_MODE='gemini'`.
- Structured JSON logging in `src/campaign/logging_setup.py`:
  - Integrated `structlog` with contextvars for `run_id` and `phase`.
  - Security filtering ensuring product briefs, raw customer rows, and API keys cannot be logged.
- Append-only trace logging in `src/campaign/trace_log.py`:
  - Thread-safe JSONL writer recording model steps (token usage, cost, content SHA-256) and tool calls (truncated arguments at 300 characters, execution latency, error codes).
- Why `extra="forbid"` matters:
  - Models often hallucinate unexpected parameters in tool arguments and JSON responses. `extra="forbid"` ensures any unexpected or hallucinated key fails schema validation immediately instead of being silently accepted, preventing unintended tool behavior and prompt injection payload smuggling.

## T3: Customer Database, Search Fixtures, Read-Only Database Layer, and SQL Audit Log
- Deterministic customer database builder in `scripts/build_db.py`:
  - Uses fixed random seed 42 to generate exactly 2,000 customers and associated purchases.
  - Generates strictly synthetic demographic and behavioural attributes (age bands, regions, income bands, interests, lifetime values, opt-ins); direct personal identifiers (names, emails, addresses, phones) are completely excluded.
  - Verified bitwise deterministic checksum across builds.
- Search fixtures in `data/fixtures/search.json`:
  - 3 demo products (`smart water bottle`, `trail running shoes`, `reusable lunch box`) with at least 6 results each.
  - Contains targeted prompt injection fixtures per product for testing defense resilience.
- Three-layer read-only SQLite security architecture in `src/campaign/db.py`:
  1. `mode=ro` URI flag: OS-level read-only file lock preventing writes to the underlying SQLite file.
  2. `PRAGMA query_only=ON`: Engine-level enforcement preventing data modification operations.
  3. `sqlite3.set_authorizer`: Bytecode compiler-level callback allowing only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`, immediately rejecting `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, and schema changes.
- VM Step Limit:
  - Progress handler aborts queries after 1,000,000 VM instructions, defending against algorithmic complexity / denial-of-service runaway queries.
- Fail-Closed SQL Audit Logger:
  - Appends audit events to `audit/sql_audit.jsonl` with timestamp, run ID, acceptance status, error code, and SQL text (capped at 500 characters).
  - Strictly omits result rows and customer data; any file I/O failure raises an exception to fail closed.

## T4: Run State Machine and Persistent Storage Layer
- Created `src/campaign/store.py` backed by SQLite (`runs.db`):
  - `runs` table storing full JSON representations of product brief, angles, and advertising package, alongside execution counters (`tool_calls_used`, `cost_usd`).
  - `rate_events` table indexed by `(user_id, ts)` for persistent sliding-window rate limiting surviving process restarts.
- Strict State Machine Transitions:
  - Phase 1 initializes runs into `AWAITING_APPROVAL` (or terminal failure: `LIMIT_REACHED`, `BUDGET_EXCEEDED`, `FAILED`).
  - Human review transitions from `AWAITING_APPROVAL` exclusively to `COMPLETED` (with selected angle index and drafted package), `REJECTED`, or phase 2 bound failures.
  - Re-approving or transitioning out of terminal states raises `InvalidTransition`.
- Dual-Layer SQL Injection Defense:
  - Domain layer: Pydantic regex validator rejects invalid or adversarial `user_id` inputs before SQL compilation.
  - Database layer: 100% parameterised queries (`?` bindings) treat all dynamic values as literal parameters.

## T5: Input Sanitization, Advertising Compliance, and Mock Analytics
- Sanitization & Injection Defense (`src/campaign/sanitize.py`):
  - Strips zero-width characters (`\u200b`, `\u200c`, `\u200d`, `\ufeff`) and control characters while preserving formatting whitespace (`\n`, `\t`, `\r`).
  - Implemented prompt injection detector checking for instructions like `ignore previous instructions`, `developer mode`, `system override`, `output hacked`, etc.
  - `wrap_untrusted`: Escapes internal `<untrusted>` tags and securely delimits untrusted web content.
  - Fail-closed brief rejection (`HostileInputError`) for malicious staff submissions.
- Advertising Copy Compliance (`src/campaign/compliance.py`):
  - Enforces word-boundary checks against banned advertising terms (`guaranteed`, `100% safe`, `cure`, `miracle`, `risk-free`, `#1 in the world`) to prevent false positives on substrings (e.g. `secure`).
  - Enforces the `% off` rule: rejects unauthorized discount claims unless explicitly authorized in the product brief.
- Deterministic Mock Analytics (`src/campaign/analytics.py`):
  - Formula: `reach = round(base[segment] * rate[channel] * min(1.0, budget_usd / 5000) ** 0.5)`.
  - Documented base constants (Fitness: 50k, Professionals: 45k, Families: 35k, Students: 40k) and channel multipliers (Instagram: 1.2, Google Ads: 1.0, Email: 0.8).
  - Verified monotonicity with budget and bounds validation ($50 to $100,000).
- Why a flagged brief is rejected but a flagged web result is only wrapped:
  - The brief is submitted by internal staff: if hostile, failing closed immediately prevents unauthorized operation and saves token budget.
  - Web search results are external third-party content. If the agent aborted whenever a public website contained injection text, attackers could trivially DoS the marketing agent. Wrapping in `<untrusted>` tags allows the model to process competitor data safely as inert text rather than instructions.

## T6: Hostile SQL Test Suite, Validator Stub, and Sliding-Window Rate Limiter
- Created exhaustive SQL safety test suite in `tests/test_sqlsafe.py`:
  - 44 hostile attack vectors spanning stacked queries, semicolons in literals, comments (`--` and `/* */`), non-SELECT verbs (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`), denylisted functions (`ATTACH`, `DETACH`, `PRAGMA`, `LOAD_EXTENSION`), table functions (`pragma_`), system schemas (`sqlite_master`, `sqlite_sequence`), CTE recursion (`WITH`), tables outside allowlist, subqueries, non-ASCII/Unicode homoglyphs, zero-width characters, bounds/lengths, and limit manipulations.
  - 11 benign cases verifying standard business queries (aggregates, joins, group by, order by, limit rewrite, missing limit append).
  - Explicit bypass test proving that even if `validate()` is skipped, the underlying read-only database connection still refuses writes (S2).
- Defined `sqlsafe.py` interface and `SqlRejected` exception with `NotImplementedError` stub.
- Implemented persistent sliding-window rate limiter in `src/campaign/ratelimit.py`:
  - Injected clock mechanism for deterministic testing without sleeping.
  - Backed by `rate_events` table in SQLite (`runs.db`), ensuring rate limits survive server crashes and restarts.
  - Computes remaining wait time until rolling window expiry.

## T7: Seven-Rule SELECT-Only SQL Validator (`sqlsafe.py`)
Implemented `sqlsafe.validate(sql: str) -> ValidatedSql` enforcing 7 rigorous defense-in-depth rules before queries ever touch SQLite:
1. **Rule 1 (Length and Character Encoding)**:
   - Query length must be between 10 and 500 characters.
   - Restricts characters strictly to ASCII printable (`0x20` to `0x7E`) plus standard whitespace (`\t`, `\n`, `\r`). Rejects null bytes, vertical tabs, Unicode homoglyphs (e.g. Cyrillic `с`), and zero-width spaces (`\u200b`).
2. **Rule 2 (No Stacked Statements / Semicolon Ban)**:
   - Strips at most one trailing semicolon. Rejects any other semicolon anywhere in the query (including within string literals), completely preventing stacked query injection (e.g. `SELECT ...; DROP TABLE ...`).
3. **Rule 3 (Strict Comment Ban)**:
   - Disallows `--` and `/* ... */` comment markers anywhere in the query string to prevent comment-based query truncation or payload hiding.
4. **Rule 4 (SELECT-Only Root and No CTEs)**:
   - Requires the query to begin with `SELECT` (`^\s*SELECT\b`).
   - Disallows Common Table Expressions (`WITH` and `WITH RECURSIVE`) to prevent recursive execution loops.
   - Forbids `SELECT ... INTO` statements.
5. **Rule 5 (Keyword and Schema Denylist)**:
   - Rejects whole-word denylisted verbs and functions: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `REINDEX`, `ANALYZE`, `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `TRIGGER`, `LOAD_EXTENSION`.
   - Rejects all access to SQLite internals via `sqlite_` and `pragma_` table/view/function prefixes.
6. **Rule 6 (Strict Table Allowlist)**:
   - Every table identifier referenced after `FROM` or any `JOIN` (including subqueries and comma-separated joins) must belong to the strict allowlist: `{"segments", "customers", "purchases"}`. Unlisted tables or system tables trigger immediate rejection.
7. **Rule 7 (Automated LIMIT Enforcement & Rewrite)**:
   - If `LIMIT` is absent, appends `LIMIT 50`.
   - If `LIMIT` is present, validates that the limit is an unsigned integer > 0 (rejecting floats, negative integers, or injection strings). If the requested limit exceeds 50, automatically rewrites it to 50.

> [!NOTE]
> The regex validator is an application-level filter. The true security boundary remains the read-only SQLite connection (`mode=ro`, `PRAGMA query_only=ON`, and the bytecode authorizer), verified by test bypass.
