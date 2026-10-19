"""SELECT-only SQL query validator (Stub for T6)."""

from __future__ import annotations

from dataclasses import dataclass


class SqlRejected(ValueError):
    """Raised when an SQL query fails safety validation rules."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


@dataclass(frozen=True)
class ValidatedSql:
    """Safe, validated, and normalized SQL query ready for execution."""

    raw_sql: str
    sanitized_sql: str


def validate(sql: str) -> ValidatedSql:
    """Validate that the query is a safe SELECT statement conforming to all 7 rules.

    Raises:
        SqlRejected: If any of the 7 safety rules are violated.
        NotImplementedError: In T6 before full implementation in T7.
    """
    raise NotImplementedError("sqlsafe.validate is implemented in T7")
