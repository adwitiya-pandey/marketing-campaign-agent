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
