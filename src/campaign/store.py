"""Run store and state machine persistence in SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from campaign.config import get_settings
from campaign.models import (
    CampaignAngles,
    CampaignPackage,
    ProductBrief,
    RunRecord,
    RunStatus,
)


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""


RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    product_json TEXT NOT NULL,
    angles_json TEXT,
    selected_index INTEGER,
    package_json TEXT,
    tool_calls_used INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_events_user_ts ON rate_events (user_id, ts);
"""

# State transitions: only AWAITING_APPROVAL can transition into terminal states
VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    "AWAITING_APPROVAL": {
        "COMPLETED",
        "REJECTED",
        "LIMIT_REACHED",
        "BUDGET_EXCEEDED",
        "FAILED",
    },
    "COMPLETED": set(),
    "REJECTED": set(),
    "LIMIT_REACHED": set(),
    "BUDGET_EXCEEDED": set(),
    "FAILED": set(),
}


class RunStore:
    """Manages persistent runs and rate limit events in runs.db."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else settings.runs_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(RUNS_SCHEMA)
            conn.commit()

    def create_run(self, record: RunRecord) -> None:
        """Persist a new run record using parameterised SQL."""
        product_json = record.product.model_dump_json()
        angles_json = record.angles.model_dump_json() if record.angles else None
        package_json = record.package.model_dump_json() if record.package else None

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, user_id, status, product_json, angles_json,
                    selected_index, package_json, tool_calls_used, cost_usd,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.user_id,
                    record.status,
                    product_json,
                    angles_json,
                    record.selected_index,
                    package_json,
                    record.tool_calls_used,
                    record.cost_usd,
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        """Retrieve a run record by run_id using parameterised SQL."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def _row_to_record(self, row: sqlite3.Row) -> RunRecord:
        product = ProductBrief.model_validate_json(row["product_json"])
        angles = (
            CampaignAngles.model_validate_json(row["angles_json"]) if row["angles_json"] else None
        )
        package = (
            CampaignPackage.model_validate_json(row["package_json"])
            if row["package_json"]
            else None
        )

        return RunRecord(
            run_id=row["run_id"],
            user_id=row["user_id"],
            status=row["status"],
            product=product,
            angles=angles,
            selected_index=row["selected_index"],
            package=package,
            tool_calls_used=row["tool_calls_used"],
            cost_usd=row["cost_usd"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_runs(self, limit: int = 100) -> list[RunRecord]:
        """List recent runs ordered by creation time descending."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def transition_run(
        self,
        run_id: str,
        new_status: RunStatus,
        *,
        selected_index: int | None = None,
        package: CampaignPackage | None = None,
        tool_calls_used: int | None = None,
        cost_usd: float | None = None,
    ) -> RunRecord:
        """Validate and apply state transition for an existing run."""
        current = self.get_run(run_id)
        if not current:
            raise KeyError(f"Run {run_id} not found")

        # Validate state machine transition rules
        allowed_targets = VALID_TRANSITIONS.get(current.status, set())
        if new_status not in allowed_targets:
            raise InvalidTransition(
                f"Invalid transition: cannot move from {current.status} to {new_status}"
            )

        now_iso = datetime.now(UTC).isoformat()
        updated_index = selected_index if selected_index is not None else current.selected_index
        updated_package = package if package is not None else current.package
        package_json = updated_package.model_dump_json() if updated_package else None
        updated_tools = tool_calls_used if tool_calls_used is not None else current.tool_calls_used
        updated_cost = cost_usd if cost_usd is not None else current.cost_usd

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, selected_index = ?, package_json = ?,
                    tool_calls_used = ?, cost_usd = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    new_status,
                    updated_index,
                    package_json,
                    updated_tools,
                    updated_cost,
                    now_iso,
                    run_id,
                ),
            )
            conn.commit()

        return self.get_run(run_id)  # type: ignore[return-value]

    # Rate limiting event helpers
    def record_rate_event(self, user_id: str, ts: float) -> None:
        """Record a timestamped rate limit event for a user."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO rate_events (user_id, ts) VALUES (?, ?)",
                (user_id, ts),
            )
            conn.commit()

    def count_rate_events(self, user_id: str, window_start_ts: float) -> int:
        """Count active rate events for a user within a rolling window."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM rate_events WHERE user_id = ? AND ts >= ?",
                (user_id, window_start_ts),
            )
            return cursor.fetchone()[0]

    def get_oldest_rate_event_ts(self, user_id: str, window_start_ts: float) -> float | None:
        """Get timestamp of oldest active rate event in rolling window."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT MIN(ts) FROM rate_events WHERE user_id = ? AND ts >= ?",
                (user_id, window_start_ts),
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else None

    def clean_old_rate_events(self, cutoff_ts: float) -> None:
        """Clean rate events older than cutoff timestamp."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM rate_events WHERE ts < ?", (cutoff_ts,))
            conn.commit()
