"""Tests for customer database construction, constraints, and read-only protections."""

import hashlib
import sqlite3

import pytest

from campaign.db import (
    DatabaseSecurityError,
    execute_readonly_query,
    get_readonly_connection,
)
from scripts.build_db import build_database


def test_database_build_deterministic(tmp_path):
    db1 = tmp_path / "db1.db"
    db2 = tmp_path / "db2.db"
    build_database(db1, seed=42)
    build_database(db2, seed=42)

    # Verify checksums match exactly
    h1 = hashlib.sha256(db1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(db2.read_bytes()).hexdigest()
    assert h1 == h2


def test_database_check_constraints(tmp_path):
    db_file = tmp_path / "test.db"
    build_database(db_file, seed=42)

    conn = sqlite3.connect(str(db_file))
    # Test invalid age_band
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO customers VALUES (9999, 'students', 'invalid_band', 'North', 'mid', 'tech', 100.0, 1)"
        )
    # Test negative lifetime_value
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO customers VALUES (9999, 'students', '18-24', 'North', 'mid', 'tech', -10.0, 1)"
        )
    # Test invalid email_opt_in
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO customers VALUES (9999, 'students', '18-24', 'North', 'mid', 'tech', 10.0, 2)"
        )
    conn.close()


def test_readonly_connection_blocks_writes(tmp_path):
    """Test S2: connection refuses all write/schema alterations even if validate is bypassed."""
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)
    audit_file = tmp_path / "audit.jsonl"

    forbidden_queries = [
        "INSERT INTO customers (customer_id, segment, age_band, region, income_band, interest, lifetime_value, email_opt_in) VALUES (9999, 'students', '18-24', 'North', 'mid', 'tech', 10.0, 1)",
        "UPDATE customers SET lifetime_value = 0 WHERE customer_id = 1",
        "DELETE FROM customers WHERE customer_id = 1",
        "DROP TABLE customers",
        "ATTACH DATABASE ':memory:' AS evil",
        "PRAGMA user_version = 42",
        "CREATE TABLE backdoor(x INTEGER)",
    ]

    for sql in forbidden_queries:
        with pytest.raises((DatabaseSecurityError, sqlite3.DatabaseError)):
            execute_readonly_query(
                sql,
                db_path=db_file,
                run_id="RUN-20261019-0001",
                audit_path=audit_file,
            )


def test_readonly_select_success_and_truncation(tmp_path):
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)
    audit_file = tmp_path / "audit.jsonl"

    # Query 1: small result
    res = execute_readonly_query(
        "SELECT customer_id, segment, age_band FROM customers LIMIT 10",
        db_path=db_file,
        run_id="RUN-20261019-0001",
        audit_path=audit_file,
    )
    assert len(res["rows"]) == 10
    assert res["columns"] == ["customer_id", "segment", "age_band"]
    assert res["truncated"] is False

    # Query 2: > 50 rows -> truncated
    res_trunc = execute_readonly_query(
        "SELECT customer_id FROM customers",
        db_path=db_file,
        run_id="RUN-20261019-0001",
        audit_path=audit_file,
        max_rows=50,
    )
    assert len(res_trunc["rows"]) == 50
    assert res_trunc["truncated"] is True


def test_runaway_query_aborted_by_step_limit(tmp_path):
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)

    runaway_sql = "SELECT count(*) FROM customers a, customers b, customers c"

    # Use low step limit to quickly trigger abort
    conn = get_readonly_connection(db_file, step_limit=5000)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(runaway_sql)
    conn.close()
