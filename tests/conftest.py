"""Pytest configuration and environment isolation."""

import os

# Ensure LangSmith tracing is explicitly disabled in tests before imports
os.environ["LANGSMITH_TRACING"] = "false"
