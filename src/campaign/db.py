"""Read-only SQLite database access layer with audit logging."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from campaign.config import get_settings

_AUDIT_LOCK = threading.Lock()
MAX_VM_STEPS = 1_000_000
PROGRESS_INTERVAL = 1_000


class DatabaseSecurityError(sqlite3.DatabaseError):
    """Raised when an unauthorized or unsafe database operation is detected."""


class QueryAbortedError(sqlite3.OperationalError):
    """Raised when a query exceeds VM execution step limits."""


def authorizer_callback(
    action_code: int,
    param1: str | None,
    param2: str | None,
    db_name: str | None,
    trigger_name: str | None,
) -> int:
    """Allow only SELECT, READ, and FUNCTION operations."""
    if action_code in (
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    ):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def record_sql_audit(
    *,
    audit_path: Path | str,
    run_id: str,
    accepted: bool,
    code: str | None,
    sql: str,
    row_count: int,
) -> None:
    """Append-only, fail-closed SQL audit logging without row data."""
    path = Path(audit_path)
    capped_sql = sql[:500] if len(sql) > 500 else sql

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "accepted": accepted,
        "code": code,
        "sql": capped_sql,
        "row_count": row_count,
    }

    line = json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n"

    # Fail-closed: do not swallow any IOError/OSError
    with _AUDIT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def get_readonly_connection(
    db_path: Path | str,
    step_limit: int = MAX_VM_STEPS,
) -> sqlite3.Connection:
    """Open a single-call read-only connection with PRAGMA query_only and authorizer."""
    path = Path(db_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {path}")

    # Layer 1: URI read-only mode
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0)

    # Layer 2: PRAGMA query_only = ON
    conn.execute("PRAGMA query_only = ON;")

    # Layer 3: Authorizer allowing SELECT, READ, FUNCTION only
    conn.set_authorizer(authorizer_callback)

    # Step limit progress handler
    steps_executed = [0]

    def progress_handler() -> int:
        steps_executed[0] += PROGRESS_INTERVAL
        if steps_executed[0] > step_limit:
            return 1  # Abort query
        return 0

    conn.set_progress_handler(progress_handler, PROGRESS_INTERVAL)
    return conn


def execute_readonly_query(
    sql: str,
    *,
    db_path: Path | str | None = None,
    run_id: str = "UNKNOWN",
    audit_path: Path | str | None = None,
    max_rows: int = 50,
) -> dict[str, Any]:
    """Execute a read-only SELECT query through guarded connection with audit logging."""
    settings = get_settings()
    target_db = Path(db_path) if db_path else settings.customers_db
    target_audit = Path(audit_path) if audit_path else settings.sql_audit_path

    conn = get_readonly_connection(target_db)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        # Fetch max_rows + 1 to detect truncation
        fetched = cursor.fetchall()
        truncated = len(fetched) > max_rows
        rows = [list(r) for r in fetched[:max_rows]]

        # Record audit success
        record_sql_audit(
            audit_path=target_audit,
            run_id=run_id,
            accepted=True,
            code=None,
            sql=sql,
            row_count=len(rows),
        )

        return {
            "columns": columns,
            "rows": rows,
            "truncated": truncated,
        }
    except sqlite3.OperationalError as e:
        err_msg = str(e).lower()
        if "interrupted" in err_msg or "step limit" in err_msg:
            record_sql_audit(
                audit_path=target_audit,
                run_id=run_id,
                accepted=False,
                code="QUERY_STEP_LIMIT_EXCEEDED",
                sql=sql,
                row_count=0,
            )
            raise QueryAbortedError(f"Query step limit exceeded: {e}") from e

        record_sql_audit(
            audit_path=target_audit,
            run_id=run_id,
            accepted=False,
            code="SQLITE_OPERATIONAL_ERROR",
            sql=sql,
            row_count=0,
        )
        raise
    except Exception as e:
        record_sql_audit(
            audit_path=target_audit,
            run_id=run_id,
            accepted=False,
            code="SECURITY_VIOLATION",
            sql=sql,
            row_count=0,
        )
        raise DatabaseSecurityError(f"Database security rejection: {e}") from e
    finally:
        conn.close()
