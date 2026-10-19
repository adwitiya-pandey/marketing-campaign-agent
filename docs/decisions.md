# Marketing Campaign Agent: Architectural Decision Log

This document records the core architectural decisions made in the development of the marketing campaign agent, their rationale, alternatives rejected, and explicit criteria that would prompt reconsidering them.

---

### D1: Use `langchain.agents.create_agent` with Middleware Instead of Legacy `AgentExecutor`
- **Context**: The curriculum brief mentions `AgentExecutor`, which in LangChain 1.x was relegated to the legacy `langchain-classic` package.
- **Decision**: Build the agent using modern `langchain.agents.create_agent` with tool and model limit middlewares.
- **Rejected**: `langchain-classic.AgentExecutor` and custom manual LangGraph state graphs.
- **Rationale**: `create_agent` is the supported standard in LangChain 1.x. It cleanly accepts middleware for tool limits, cost ceilings, and step bounds without introducing unneeded graph complexity.
- **What would change my mind**: If LangChain deprecates `create_agent` or introduces breaking middleware incompatibilities that cannot be resolved without raw LangGraph nodes.

---

### D2: Single ReAct Agent per Phase Instead of Multi-Agent Crew
- **Context**: Campaign creation involves distinct research, analysis, and copywriting activities.
- **Decision**: Use a single ReAct-style agent with specialized tools for each phase (Phase 1 for research/angles; Phase 2 for copy drafting).
- **Rejected**: Multi-agent swarms (CrewAI, AutoGen, multi-agent LangGraph).
- **Rationale**: A multi-agent network introduces non-deterministic communication loops, quadruples token consumption, and adds unnecessary complexity for a deterministic 2-phase workflow.
- **What would change my mind**: If the product requirements expanded to require real-time adversarial debate between specialized agent roles (e.g. Compliance Agent vetoing Creative Agent in real time).

---

### D3: Human Gate Orchestrated in Code (`service.py`) Instead of In-Agent Pause
- **Context**: A human marketing manager must review 5 angles and approve one before Phase 2 copy drafting begins.
- **Decision**: Implement the human gate as an explicit application orchestrator method (`CampaignService.approve_angle`) that reads the approved angle by index from persistent storage.
- **Rejected**: In-agent execution pauses (e.g., waiting on input inside a running agent loop).
- **Rationale**: Pausing a live agent loop holds memory, risks process timeout, and does not survive server restarts. Managing state in SQLite allows indefinite review delays and clean restart safety.
- **What would change my mind**: If LangGraph checkpointers provide zero-overhead persistent resumption that matches the simplicity of a pure relational table transition.

---

### D4: Explicit Pydantic Code Validation Instead of Model `response_format`
- **Context**: The model must return exactly 5 campaign angles in Phase 1 and a complete multi-channel package in Phase 2.
- **Decision**: Validate the final model message in Python code using `CampaignAngles.model_validate_json()` and `CampaignPackage.model_validate_json()`, with exactly one repair turn on failure.
- **Rejected**: Using Gemini native `response_format={"type": "json_object"}` alongside active tool calling.
- **Rationale**: Combining native JSON structured output with tool calling is unverified and unreliable across diverse Gemini versions. Code validation is transparent, testable, and allows fine-grained error feedback.
- **What would change my mind**: If official SDK benchmarks prove 100% reliability for simultaneous function-calling and strict JSON schemas across all supported LLM providers.

---

### D5: Multi-Layer SQLite Security Boundary Instead of Validator Alone
- **Context**: The agent generates dynamic SQL queries over the customer database.
- **Decision**: Enforce security through a strict 7-rule validator in `sqlsafe.py` backed by a 3-layer read-only SQLite connection (`mode=ro`, `PRAGMA query_only=ON`, and bytecode authorizer callback).
- **Rejected**: Relying solely on regex/AST query validation or relying solely on database permissions.
- **Rationale**: Defense in depth. Regex and AST validators can have grammar edge-case bypasses; the SQLite connection engine authorizer serves as an absolute barrier against modifications.
- **What would change my mind**: If SQLite were replaced with an enterprise database engine that enforces cryptographically verifiable read-only connection tokens at the network protocol layer.

---

### D6: Middleware-Enforced Resource Limits Instead of Prompt Instructions
- **Context**: The agent must adhere strictly to a 15-tool-call limit and a $0.25 cost ceiling per run.
- **Decision**: Enforce limits via LangChain middleware (`ToolCallLimitMiddleware` and custom `CostCeilingMiddleware` raising `BudgetExceeded`).
- **Rejected**: Prompt instructions ("Do not make more than 15 tool calls").
- **Rationale**: Prompts are suggestions, not security controls. Models regularly ignore prompt-based count constraints. Middleware provides hard software boundaries.
- **What would change my mind**: Nothing. Safety, resource, and financial limits must always be enforced by software controls, never by prompt instructions.

---

### D7: Fixture-Based Search by Default Instead of Mandatory Live Search
- **Context**: Phase 1 queries competitor and industry data.
- **Decision**: Default to a verified local search fixture (`data/fixtures/search.json`), with optional DuckDuckGo search behind an extra dependency.
- **Rejected**: Requiring live search API keys or unmocked web scrapers for all runs.
- **Rationale**: Guarantees deterministic, reproducible, 100% offline testing without network flakiness, rate limits, or external dependencies.
- **What would change my mind**: If the primary business objective shifted to real-time breaking news analysis where stale fixtures provide no evaluation value.

---

### D8: Scripted Demo Mode as Default Instead of Requiring Live API Key
- **Context**: Users and hiring managers cloning the repo need to verify functionality quickly.
- **Decision**: Default to `LLM_MODE=scripted` using `ScriptedChatModel` with prominent UI and CLI banners.
- **Rejected**: Failing immediately on clone if `GEMINI_API_KEY` is not set.
- **Rationale**: Anyone can clone and run the full end-to-end workflow in seconds without registering for API keys.
- **What would change my mind**: If the project's goal were purely production SaaS deployment rather than an open-source demonstrable reference codebase.

---

### D9: Notional Cost Calculation Based on Published Token Rates
- **Context**: Displaying per-run financial cost in the dashboard and cost report.
- **Decision**: Calculate cost motionally (`tokens * rate`), with explicit caveats that free-tier API calls bill $0.00.
- **Rejected**: Attempting to query live billing APIs or claiming zero cost because of the free tier.
- **Rationale**: Real-time billing APIs have multi-hour reporting delays and require admin privileges. Notional token pricing gives realistic economic estimates for commercial deployments.
- **What would change my mind**: If Gemini provides real-time transaction-level billing metadata returned directly in model response headers.

---

### D10: SQLite Storage for State and Rate Limiting Instead of In-Memory Maps
- **Context**: Tracking active runs and sliding-window rate limit events.
- **Decision**: Store runs and rate events in SQLite databases (`runs.db`).
- **Rejected**: In-memory Python dictionaries or external Redis servers.
- **Rationale**: In-memory state is wiped on server restarts, allowing users to bypass rate limits by rebooting the app. Redis introduces external infrastructure requirements. SQLite offers zero-dependency persistence.
- **What would change my mind**: If the application scales to a distributed multi-node cluster where a local file-based database cannot be shared across pods.
