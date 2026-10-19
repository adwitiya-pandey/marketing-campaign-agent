"""Tests for fail-closed SQL audit logging."""

import json

import pytest

from campaign.db import execute_readonly_query, record_sql_audit
from scripts.build_db import build_database


def test_sql_audit_fields_and_no_row_data(tmp_path):
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)
    audit_file = tmp_path / "sql_audit.jsonl"

    sql = "SELECT customer_id, segment, lifetime_value FROM customers LIMIT 5"
    res = execute_readonly_query(
        sql,
        db_path=db_file,
        run_id="RUN-20261019-0001",
        audit_path=audit_file,
    )
    assert len(res["rows"]) == 5

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    audit_entry = json.loads(lines[0])

    # Check required fields
    assert audit_entry["run_id"] == "RUN-20261019-0001"
    assert audit_entry["accepted"] is True
    assert audit_entry["code"] is None
    assert audit_entry["sql"] == sql
    assert audit_entry["row_count"] == 5
    assert "ts" in audit_entry

    # S3: Verify NO row data is present in audit log
    for row in res["rows"]:
        for val in row:
            if isinstance(val, (int, float)) and val > 10:
                assert str(val) not in lines[0]


def test_sql_audit_failure_raises(tmp_path):
    """Test S3: audit failure stops execution fail-closed."""
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)

    # Use a directory path as the audit file to induce an IOError/IsADirectoryError
    invalid_audit_dir = tmp_path / "invalid_audit_dir"
    invalid_audit_dir.mkdir()

    with pytest.raises(OSError):
        record_sql_audit(
            audit_path=invalid_audit_dir,
            run_id="RUN-20261019-0001",
            accepted=True,
            code=None,
            sql="SELECT 1",
            row_count=1,
        )
