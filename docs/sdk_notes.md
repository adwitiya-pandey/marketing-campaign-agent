# SDK notes

Pre-filled on 17 and 18 Oct 2026 by running langchain 1.4.6, langchain-core 1.6.12, langchain-google-genai 4.4.2, langsmith 0.14.11, streamlit 1.66.0, pydantic 2.12.5 and google-genai 2.31.0 in a throwaway Python 3.13.16 environment. **The coding agent must re-run the probe below against the versions `uv` installs and correct this file where anything differs.** Anything not listed here is unverified: do not guess.

## Verified imports
```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallLimitMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
```
`from langchain_classic.agents import AgentExecutor` also works but is the legacy package (`langchain-classic`); this project does not use it.

## Verified behaviour
| Topic | Result |
|---|---|
| `create_agent` signature | `create_agent(model, tools=None, *, system_prompt=None, middleware=(), response_format=None, state_schema=None, context_schema=None, checkpointer=None, store=None, interrupt_before=None, interrupt_after=None, debug=False, name=None, cache=None, transformers=None)`; returns a compiled graph; call `agent.invoke({"messages": [HumanMessage(...)]}, config={"recursion_limit": 30})`. |
| Middleware hooks | `AgentMiddleware` has `before_agent`, `before_model`, `after_model`, `after_agent`, `wrap_model_call`, `wrap_tool_call` and async versions. |
| `ToolCallLimitMiddleware` | `__init__(*, tool_name=None, thread_limit=None, run_limit=None, exit_behavior="continue")`. With `run_limit=2`, `exit_behavior="end"` and a model that asks for 5 calls: 3 `ToolMessage`s appear, the last text is `Tool call limit reached: run limit exceeded (3/2 calls).` and the run ended normally. So the first 2 calls executed and the third was blocked; do not count the blocking message as an executed call. |
| `ModelCallLimitMiddleware` | `__init__(*, thread_limit=None, run_limit=None, exit_behavior="end")` (`"end"` or `"error"`). |
| Custom cost ceiling | A subclass of `AgentMiddleware` with `after_model(self, state, runtime)` reading `state["messages"][-1].usage_metadata` (`input_tokens`, `output_tokens`) and raising a custom exception: the exception **propagated out of `agent.invoke`** after the model call that crossed the ceiling. |
| Fake model | `class FakeToolModel(GenericFakeChatModel): def bind_tools(self, tools, **kw): return self`; `FakeToolModel(messages=iter([AIMessage(content="", tool_calls=[{"name": "search", "args": {"query": "x"}, "id": "c0"}], usage_metadata={...}), AIMessage(content="done")]))` drives a real tool loop. |
| Tool schemas | `@tool(args_schema=PydanticModel)` works; `tool.args_schema.model_json_schema()["properties"]` lists the fields. |
| Gemini model | `ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key="dummy", temperature=0, max_retries=2)` constructs offline. Verified fields include `model`, `google_api_key`, `temperature`, `max_output_tokens`, `max_retries`, `timeout`, `thinking_budget`. `gemini-3.8-flash` is listed Stable on the official Gemini models page (17 Oct 2026). |
| Callbacks | `BaseCallbackHandler` has `on_llm_end`, `on_tool_start`, `on_tool_end`, `on_tool_error`, `on_chat_model_start`. |
| LangSmith | `langsmith.utils.tracing_is_enabled()` returns `False` when `LANGSMITH_TRACING=false`. |
| Streamlit tests | `from streamlit.testing.v1 import AppTest`; `AppTest.from_file(path)` exists. |

## Not verified (decide with evidence, record in `docs/decisions.md` or `docs/open_questions.md`)
1. Multi-step tool calling with Gemini 3.x through `langchain-google-genai` 4.4.2 (Gemini 3 models may require "thought signatures" to be passed back between function-call turns; check the Gemini function-calling docs and test in T14 before claiming it works).
2. `response_format` together with tools on Gemini (this project avoids it: SPEC D4).
3. Whether `usage_metadata` on Gemini replies includes thinking tokens (T14 compares with the Gemini usage page).
4. The `ddgs` package (9.16.0) for the optional live search backend: behaviour, rate limits and terms not checked; the default is the fixture backend.
5. Gemini free-tier rate limits and data-use terms.
6. Whether LangSmith traces show tool calls and token usage for Gemini through `ChatGoogleGenerativeAI` (T14 checks real traces and takes screenshots).

## Probe (re-run; `uv run python -I probe.py` from a scratch folder, not committed)
```python
import os

os.environ["LANGSMITH_TRACING"] = "false"
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


class Args(BaseModel):
    query: str = Field(min_length=3, max_length=200)


@tool(args_schema=Args)
def search(query: str) -> str:
    """Search the web."""
    return "result for " + query


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


USAGE = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}


def script(n):
    msgs = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {"query": f"query {i}"}, "id": f"c{i}"}],
            usage_metadata=USAGE,
        )
        for i in range(n)
    ]
    msgs.append(AIMessage(content="done", usage_metadata=USAGE))
    return iter(msgs)


# 1) tool limit: run_limit=2, model wants 5
agent = create_agent(
    model=FakeToolModel(messages=script(5)),
    tools=[search],
    middleware=[ToolCallLimitMiddleware(run_limit=2, exit_behavior="end")],
)
r = agent.invoke({"messages": [HumanMessage("go")]}, config={"recursion_limit": 30})
tool_msgs = [m for m in r["messages"] if m.type == "tool"]
print("tool messages:", len(tool_msgs), "| last:", repr(r["messages"][-1].content)[:70])


# 2) cost ceiling raised from after_model propagates out of invoke
class BudgetExceeded(Exception):
    pass


class Cost(AgentMiddleware):
    def __init__(self, ceiling):
        super().__init__()
        self.ceiling, self.spent, self.calls = ceiling, 0.0, 0

    def after_model(self, state, runtime):
        u = state["messages"][-1].usage_metadata or {}
        self.spent += u.get("input_tokens", 0) * 1e-6 + u.get("output_tokens", 0) * 4e-6
        self.calls += 1
        if self.spent > self.ceiling:
            raise BudgetExceeded(f"{self.spent:.4f}")
        return None


c = Cost(0.0025)
agent2 = create_agent(model=FakeToolModel(messages=script(5)), tools=[search], middleware=[c])
try:
    agent2.invoke({"messages": [HumanMessage("go")]}, config={"recursion_limit": 40})
except BudgetExceeded:
    print("BudgetExceeded propagated after", c.calls, "model calls")

# 3) Gemini model constructs offline; tool schema keys
m = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash", google_api_key="dummy", temperature=0, max_retries=2
)
print(
    "gemini:",
    type(m).__name__,
    "| tool args:",
    list(search.args_schema.model_json_schema()["properties"]),
)
```
Expected output: `tool messages: 3 | last: 'Tool call limit reached: run limit exceeded (3/2 calls).'`; `BudgetExceeded propagated after 2 model calls`; `gemini: ChatGoogleGenerativeAI | tool args: ['query']`.
