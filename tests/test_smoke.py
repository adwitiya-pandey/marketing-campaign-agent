"""Smoke test for package installation and core imports."""

from langchain.agents import create_agent

import campaign


def test_smoke_import() -> None:
    """Verify campaign package and create_agent import cleanly."""
    assert campaign is not None
    assert callable(create_agent)
