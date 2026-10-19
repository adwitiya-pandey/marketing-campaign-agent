"""Web search backends including deterministic fixture and DDGS."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from campaign.config import get_settings


class BaseSearchBackend(ABC):
    """Abstract base class for search backends."""

    @abstractmethod
    def search(self, query: str) -> list[dict[str, Any]]:
        """Execute search and return list of result dicts with title, snippet, url."""


class FixtureSearch(BaseSearchBackend):
    """Deterministic fixture search backend for offline testing and demos."""

    def __init__(self, fixture_path: Path | str = "data/fixtures/search.json") -> None:
        self.fixture_path = Path(fixture_path)
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if self.fixture_path.exists():
            content = self.fixture_path.read_text(encoding="utf-8")
            self._data = json.loads(content)
        else:
            self._data = {}

    def search(self, query: str) -> list[dict[str, Any]]:
        q_lower = query.lower()
        q_tokens = set(re_tokens(q_lower))

        # 1. Exact match on fixture keys
        for key, results in self._data.items():
            k_lower = key.lower()
            if q_lower == k_lower or k_lower in q_lower or q_lower in k_lower:
                return results

        # 2. Token overlap match
        best_match: tuple[int, list[dict[str, Any]]] = (0, [])
        for key, results in self._data.items():
            k_tokens = set(re_tokens(key.lower()))
            overlap = len(q_tokens & k_tokens)
            if overlap > best_match[0]:
                best_match = (overlap, results)

        if best_match[0] > 0:
            return best_match[1]

        return []


def re_tokens(text: str) -> list[str]:
    """Helper to extract word tokens."""
    import re

    return re.findall(r"[A-Za-z0-9]+", text)


class DdgsSearch(BaseSearchBackend):
    """Optional live search backend using duckduckgo/ddgs."""

    def search(self, query: str) -> list[dict[str, Any]]:
        try:
            from ddgs import DDGS
        except ImportError as e:
            raise ImportError(
                "ddgs package is not installed. Install with 'uv sync --extra live-search'"
            ) from e

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", ""),
                    }
                )
        return results


def get_search_backend(
    name: str | None = None,
    fixture_path: Path | str | None = None,
) -> BaseSearchBackend:
    """Factory to retrieve configured search backend instance."""
    settings = get_settings()
    backend_type = name if name is not None else settings.search_backend
    if backend_type == "ddgs":
        return DdgsSearch()
    return FixtureSearch(fixture_path or "data/fixtures/search.json")
