import os
from pathlib import Path

import pytest

from scripts.build_db import build_database

# Ensure LangSmith tracing is explicitly disabled in tests before imports
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(scope="session", autouse=True)
def setup_test_customer_database():
    """Ensure data/customers.db exists for tool tests."""
    db_path = Path("data/customers.db")
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        build_database(db_path, seed=42)
