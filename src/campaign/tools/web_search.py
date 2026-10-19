"""Web search tool for competitor and market research."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from campaign.models import WebSearchArgs
from campaign.sanitize import detect_prompt_injection, sanitize_text, wrap_untrusted
from campaign.search_backends import get_search_backend


@tool(args_schema=WebSearchArgs)
def web_search(query: str) -> str:
    """Search the web for competitor products, customer reviews, and market insights."""
    try:
        backend = get_search_backend()
        raw_results = backend.search(query)

        if not raw_results:
            return json.dumps(
                {"results": [], "message": f"No search results found for '{query}'"},
                ensure_ascii=True,
            )

        processed: list[dict[str, Any]] = []
        for r in raw_results[:5]:
            raw_snippet = r.get("snippet", "")
            is_flagged = detect_prompt_injection(raw_snippet)
            clean_snippet = sanitize_text(raw_snippet, max_length=500)
            wrapped_snippet = wrap_untrusted(clean_snippet)

            processed.append(
                {
                    "title": sanitize_text(r.get("title", ""), max_length=150),
                    "snippet": wrapped_snippet,
                    "url": r.get("url", ""),
                    "flagged": is_flagged,
                }
            )

        return json.dumps({"results": processed}, ensure_ascii=True)
    except (OSError, ValueError, KeyError) as e:
        return json.dumps({"error": f"SEARCH_ERROR: {e}"}, ensure_ascii=True)


def _handle_error(e: Exception) -> str:
    return json.dumps({"error": f"INVALID_ARG: {e}"}, ensure_ascii=True)


web_search.handle_validation_error = _handle_error
web_search.handle_tool_error = _handle_error
