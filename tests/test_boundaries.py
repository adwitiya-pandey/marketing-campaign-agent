"""Architecture boundary and safety verification via AST analysis."""

import ast
from pathlib import Path

from campaign.tools import analytics_lookup, draft_copy, sql_query, web_search

SRC_DIR = Path("src/campaign")
TOOLS_DIR = SRC_DIR / "tools"


def test_tool_name_list_snapshot():
    """Verify exact snapshot of available tool names."""
    expected_tools = ["web_search", "sql_query", "analytics_lookup", "draft_copy"]
    actual_tools = [
        web_search.name,
        sql_query.name,
        analytics_lookup.name,
        draft_copy.name,
    ]
    assert sorted(actual_tools) == sorted(expected_tools)


def test_no_write_calls_in_tools_ast():
    """AST check: verify tools perform no file write or mutation operations."""
    forbidden_calls = {"open", "write_text", "write_bytes", "remove", "unlink"}

    for py_file in TOOLS_DIR.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check direct function calls like open()
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    # If open is called, check that mode is not 'w' or 'a'
                    raise AssertionError(f"Forbidden call '{node.func.id}' found in {py_file.name}")
                # Check method calls like path.unlink() or f.write()
                if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_calls:
                    raise AssertionError(
                        f"Forbidden method '{node.func.attr}' found in {py_file.name}"
                    )


def test_no_service_import_from_agent_or_tools():
    """Verify agent.py and tools/ never import service.py (human gate isolation)."""
    checked_files = [SRC_DIR / "agent.py", *TOOLS_DIR.glob("*.py")]

    for py_file in checked_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "service" not in alias.name, (
                        f"Forbidden service import in {py_file.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "service" not in module, f"Forbidden service import in {py_file.name}"


def test_no_langchain_classic_or_agent_executor():
    """Verify legacy langchain_classic and AgentExecutor are never imported anywhere in src/."""
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain_classic" not in alias.name, (
                        f"langchain_classic found in {py_file.name}"
                    )
                    assert alias.name != "AgentExecutor", f"AgentExecutor found in {py_file.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "langchain_classic" not in module, (
                    f"langchain_classic found in {py_file.name}"
                )
                for alias in node.names:
                    assert alias.name != "AgentExecutor", f"AgentExecutor found in {py_file.name}"
