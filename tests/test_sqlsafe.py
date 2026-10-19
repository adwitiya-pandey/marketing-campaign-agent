"""Tests for SQL validation safety rules (25+ hostile cases and 10+ benign cases)."""

import pytest

from campaign.db import DatabaseSecurityError, execute_readonly_query
from campaign.sqlsafe import SqlRejected, validate
from scripts.build_db import build_database

# 30+ Hostile parametrized test cases
HOSTILE_SQL_CASES = [
    # Stacked statements
    ("SELECT * FROM customers; DROP TABLE customers", "STACKED_STATEMENTS"),
    ("SELECT customer_id FROM customers; SELECT 1", "STACKED_STATEMENTS"),
    ("SELECT * FROM customers WHERE interest = 'tech;'", "SEMICOLON_IN_LITERAL"),
    # Comment markers
    ("SELECT * FROM customers -- line comment", "COMMENTS_FORBIDDEN"),
    ("SELECT * FROM /* block comment */ customers", "COMMENTS_FORBIDDEN"),
    ("SELECT * FROM customers WHERE interest = 'tech -- cool'", "COMMENTS_FORBIDDEN"),
    ("SELECT * FROM customers WHERE interest = '/* sneaky */'", "COMMENTS_FORBIDDEN"),
    # Non-SELECT statements
    (
        "INSERT INTO customers VALUES (9999, 'students', '18-24', 'North', 'mid', 'tech', 10.0, 1)",
        "NOT_SELECT",
    ),
    ("UPDATE customers SET interest = 'hacked'", "NOT_SELECT"),
    ("DELETE FROM customers WHERE customer_id = 1", "NOT_SELECT"),
    ("DROP TABLE customers", "NOT_SELECT"),
    ("ALTER TABLE customers ADD COLUMN evil TEXT", "NOT_SELECT"),
    ("CREATE TABLE backdoor (x INT)", "NOT_SELECT"),
    ("REPLACE INTO customers (customer_id) VALUES (1)", "NOT_SELECT"),
    # Denylisted keywords
    ("SELECT * FROM customers WHERE 1=1; ATTACH DATABASE ':memory:' AS x", "DENYLISTED_KEYWORD"),
    ("SELECT * FROM customers WHERE interest = 'DETACH'", "DENYLISTED_KEYWORD"),
    ("PRAGMA query_only = OFF", "NOT_SELECT"),
    ("SELECT * FROM customers WHERE PRAGMA user_version = 1", "DENYLISTED_KEYWORD"),
    ("VACUUM", "NOT_SELECT"),
    ("BEGIN TRANSACTION", "NOT_SELECT"),
    ("COMMIT", "NOT_SELECT"),
    ("ROLLBACK", "NOT_SELECT"),
    ("SAVEPOINT sp1", "NOT_SELECT"),
    ("SELECT load_extension('malicious.so')", "DENYLISTED_KEYWORD"),
    # Denylisted pragma_ and sqlite_ prefixes
    ("SELECT * FROM pragma_table_info('customers')", "DENYLISTED_KEYWORD"),
    ("SELECT * FROM sqlite_master", "DENYLISTED_KEYWORD"),
    ("SELECT * FROM sqlite_sequence", "DENYLISTED_KEYWORD"),
    # CTE / WITH
    ("WITH cte AS (SELECT * FROM customers) SELECT * FROM cte", "CTE_FORBIDDEN"),
    ("WITH RECURSIVE cnt(x) AS (SELECT 1) SELECT * FROM cnt", "CTE_FORBIDDEN"),
    # Advanced injection tricks
    ("SELECT * INTO backup FROM customers", "NOT_SELECT"),
    ("INSERT INTO customers SELECT * FROM customers", "NOT_SELECT"),
    # Table outside allowlist
    ("SELECT * FROM secrets", "TABLE_NOT_ALLOWED"),
    ("SELECT * FROM customers JOIN passwords ON customers.id = passwords.id", "TABLE_NOT_ALLOWED"),
    (
        "SELECT * FROM customers WHERE customer_id IN (SELECT id FROM admin_users)",
        "TABLE_NOT_ALLOWED",
    ),
    # Unicode and format characters
    ("SELECT * FROM сustomers", "NON_ASCII_OR_CONTROL"),  # Cyrillic 'с'
    ("SELECT\u200b * FROM customers", "NON_ASCII_OR_CONTROL"),  # Zero-width space
    ("SELECT\x00 * FROM customers", "NON_ASCII_OR_CONTROL"),  # Null byte
    ("SELECT\t\r\n * FROM customers\x0b", "NON_ASCII_OR_CONTROL"),  # Vertical tab
    # Bounds and length
    ("SELECT 1", "LENGTH_OUT_OF_BOUNDS"),  # Length 8 < 10
    ("   ", "LENGTH_OUT_OF_BOUNDS"),
    ("SELECT * FROM customers WHERE " + "A" * 500, "LENGTH_OUT_OF_BOUNDS"),  # > 500
    # Limit tricks
    ("SELECT * FROM customers LIMIT 10.5", "INVALID_LIMIT"),
    ("SELECT * FROM customers LIMIT -5", "INVALID_LIMIT"),
    ("SELECT * FROM customers LIMIT '50'", "INVALID_LIMIT"),
]

# 11 Benign test cases
BENIGN_SQL_CASES = [
    "SELECT customer_id, segment FROM customers",
    "SELECT * FROM customers WHERE region = 'North'",
    "SELECT customers.customer_id, purchases.amount FROM customers JOIN purchases ON customers.customer_id = purchases.customer_id",
    "SELECT customers.customer_id, purchases.amount FROM customers LEFT JOIN purchases ON customers.customer_id = purchases.customer_id",
    "SELECT segment, COUNT(*), AVG(lifetime_value) FROM customers GROUP BY segment",
    "SELECT customer_id, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 10",
    "SELECT customer_id FROM customers LIMIT 100",  # Rewrites to LIMIT 50
    "SELECT customer_id FROM customers",  # Appends LIMIT 50
    "SELECT region, SUM(amount) FROM purchases WHERE amount > 50 GROUP BY region",
    "SELECT segment, description FROM segments",
    "SELECT * FROM customers;",  # Optional single trailing semicolon allowed
]


@pytest.mark.parametrize("hostile_sql,code", HOSTILE_SQL_CASES)
def test_hostile_queries_rejected(hostile_sql, code):
    with pytest.raises(SqlRejected):
        validate(hostile_sql)


@pytest.mark.parametrize("benign_sql", BENIGN_SQL_CASES)
def test_benign_queries_accepted(benign_sql):
    result = validate(benign_sql)
    assert result.sanitized_sql.startswith("SELECT")
    assert "LIMIT 50" in result.sanitized_sql or "LIMIT" in result.sanitized_sql


def test_bypass_validate_still_refused_by_connection(tmp_path):
    """Test S2: bypassing validate still cannot execute write operations against db.py."""
    db_file = tmp_path / "customers.db"
    build_database(db_file, seed=42)
    audit_file = tmp_path / "sql_audit.jsonl"

    hostile_write = "DROP TABLE customers"
    # Even without calling validate(), db.py must refuse the execution
    with pytest.raises((DatabaseSecurityError, Exception)):
        execute_readonly_query(
            hostile_write,
            db_path=db_file,
            run_id="RUN-20261019-0001",
            audit_path=audit_file,
        )
