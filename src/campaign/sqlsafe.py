"""SELECT-only SQL query validator enforcing all 7 safety rules."""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_TABLES = {"segments", "customers", "purchases"}

DENYLIST_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "ANALYZE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "TRIGGER",
    "LOAD_EXTENSION",
]


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

    Rules:
    1. Length 10..500; ASCII printable plus newline/tab only.
    2. After stripping one optional trailing ';', no other ';' anywhere.
    3. No comment markers '--' or '/*' anywhere.
    4. Must match ^\\s*SELECT\\b; WITH is rejected (no CTEs); no SELECT INTO.
    5. Keyword denylist as whole words and any sqlite_ / pragma_ identifiers.
    6. Every identifier after FROM or JOIN must be in allowed tables.
    7. LIMIT enforced: if absent append LIMIT 50; if present and > 50 rewrite to 50; non-integer rejected.
    """
    raw = sql.strip()

    # Rule 1: Length bounds 10..500
    if len(raw) < 10 or len(sql) > 500:
        raise SqlRejected(
            "LENGTH_OUT_OF_BOUNDS", "Query length must be between 10 and 500 characters"
        )

    # Rule 1: ASCII printable plus \t, \n, \r only
    for ch in sql:
        c = ord(ch)
        if c in (9, 10, 13):  # \t, \n, \r
            continue
        if c < 32 or c > 126:
            raise SqlRejected(
                "NON_ASCII_OR_CONTROL", f"Non-ASCII or control character detected: {ch!r}"
            )

    # Rule 2: Strip one optional trailing semicolon; no other semicolons anywhere
    s = raw
    if s.endswith(";"):
        s = s[:-1].strip()
    if ";" in s:
        raise SqlRejected(
            "STACKED_STATEMENTS", "Stacked statements or embedded semicolons are prohibited"
        )

    # Rule 3: No comments (-- or /* */) anywhere
    if "--" in s or "/*" in s:
        raise SqlRejected("COMMENTS_FORBIDDEN", "Comments (-- and /* */) are prohibited")

    # Rule 4: Must match ^\s*SELECT\b; WITH is rejected (no CTEs)
    if re.search(r"\bWITH\b", s, re.IGNORECASE):
        raise SqlRejected("CTE_FORBIDDEN", "Common Table Expressions (WITH) are forbidden")

    if not re.match(r"^\s*SELECT\b", s, re.IGNORECASE):
        raise SqlRejected("NOT_SELECT", "Query must start with SELECT")

    if re.search(r"\bINTO\b", s, re.IGNORECASE):
        raise SqlRejected("NOT_SELECT", "SELECT ... INTO is prohibited")

    # Rule 5: Keyword denylist as whole words, and sqlite_ / pragma_ identifiers
    for kw in DENYLIST_KEYWORDS:
        if re.search(rf"\b{kw}\b", s, re.IGNORECASE):
            raise SqlRejected("DENYLISTED_KEYWORD", f"Keyword '{kw}' is denylisted")

    if re.search(r"\b(?:sqlite_|pragma_)[A-Za-z0-9_]*", s, re.IGNORECASE):
        raise SqlRejected(
            "DENYLISTED_KEYWORD", "Access to sqlite_ and pragma_ internal schemas is denylisted"
        )

    # Rule 6: Identifiers after FROM or JOIN must be in allowed tables
    # Find all table references after FROM and JOIN
    # 1) JOIN <table_name>
    join_matches = re.finditer(
        r"\b(?:LEFT\s+|RIGHT\s+|INNER\s+|CROSS\s+)?JOIN\s+([A-Za-z0-9_]+)",
        s,
        re.IGNORECASE,
    )
    for m in join_matches:
        tbl = m.group(1).lower()
        if tbl not in ALLOWED_TABLES:
            raise SqlRejected(
                "TABLE_NOT_ALLOWED", f"Table '{tbl}' is not in allowed tables: {ALLOWED_TABLES}"
            )

    # 2) FROM <table_name> (including comma-separated tables up to the next major keyword)
    from_matches = re.finditer(
        r"\bFROM\s+([A-Za-z0-9_,\s]+?)(?=\b(?:WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|(?:LEFT\s+|RIGHT\s+|INNER\s+|CROSS\s+)?JOIN|\)|$))",
        s,
        re.IGNORECASE,
    )
    for m in from_matches:
        from_clause = m.group(1)
        items = from_clause.split(",")
        for item in items:
            tokens = item.strip().split()
            if tokens:
                tbl = tokens[0].lower()
                # Skip subquery parenthesis
                if tbl.startswith("("):
                    continue
                if tbl not in ALLOWED_TABLES:
                    raise SqlRejected(
                        "TABLE_NOT_ALLOWED",
                        f"Table '{tbl}' is not in allowed tables: {ALLOWED_TABLES}",
                    )

    # Rule 7: Enforce LIMIT (append if absent, rewrite if > 50, reject non-integers)
    limit_match = re.search(r"\bLIMIT\s+([^\s;,)]+)(.*)$", s, re.IGNORECASE)
    if limit_match:
        limit_val_raw = limit_match.group(1)
        rest = limit_match.group(2)
        if not re.fullmatch(r"[0-9]+", limit_val_raw):
            raise SqlRejected(
                "INVALID_LIMIT", f"LIMIT must be an unsigned integer, got: '{limit_val_raw}'"
            )

        limit_val = int(limit_val_raw)
        if limit_val <= 0:
            raise SqlRejected("INVALID_LIMIT", "LIMIT must be greater than 0")

        if limit_val > 50:
            # Rewrite limit to 50
            start_idx = limit_match.start()
            s = s[:start_idx] + f"LIMIT 50{rest}"
    else:
        # Append LIMIT 50
        s = f"{s} LIMIT 50"

    return ValidatedSql(raw_sql=sql, sanitized_sql=s)
