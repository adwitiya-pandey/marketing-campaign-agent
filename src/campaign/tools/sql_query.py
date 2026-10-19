"""Validated read-only SQL query tool."""

from __future__ import annotations

import json
import sqlite3

from langchain_core.tools import tool

from campaign.config import get_settings
from campaign.db import execute_readonly_query, record_sql_audit
from campaign.logging_setup import current_run_id
from campaign.models import SqlQueryArgs
from campaign.sqlsafe import SqlRejected, validate


@tool(args_schema=SqlQueryArgs)
def sql_query(query: str) -> str:
    """Execute a validated SELECT query on Brightside customer demographics and purchases."""
    run_id = current_run_id.get() or "UNKNOWN"
    settings = get_settings()

    # Step 1: Validate with 7-rule SQL validator
    try:
        validated = validate(query)
    except SqlRejected as e:
        record_sql_audit(
            audit_path=settings.sql_audit_path,
            run_id=run_id,
            accepted=False,
            code=e.code,
            sql=query,
            row_count=0,
        )
        return json.dumps({"error": f"REJECTED: {e.code}"}, ensure_ascii=True)

    # Step 2: Execute against read-only database
    try:
        res = execute_readonly_query(
            validated.sanitized_sql,
            db_path=settings.customers_db,
            run_id=run_id,
            audit_path=settings.sql_audit_path,
            max_rows=50,
        )
        return json.dumps(
            {
                "columns": res["columns"],
                "rows": res["rows"],
                "truncated": res["truncated"],
            },
            ensure_ascii=True,
        )
    except (sqlite3.Error, OSError, ValueError) as e:
        return json.dumps({"error": f"EXECUTION_ERROR: {e}"}, ensure_ascii=True)


def _handle_error(e: Exception) -> str:
    return json.dumps({"error": f"INVALID_ARG: {e}"}, ensure_ascii=True)


sql_query.handle_validation_error = _handle_error
sql_query.handle_tool_error = _handle_error
