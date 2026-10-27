"""Test that all file paths listed in the README.md repository tree exist on disk."""

from __future__ import annotations

import re
from pathlib import Path


def extract_tree_block(readme_path: Path) -> str:
    """Extract repository tree codeblock under '## Repository Structure'."""
    text = readme_path.read_text(encoding="utf-8")
    m = re.search(
        r"## Repository Structure\s*```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)\n```",
        text,
    )
    assert m is not None, "Could not find '## Repository Structure' codeblock in README.md"
    return m.group(1)


def parse_tree_paths(tree_text: str, root_dir: Path) -> list[tuple[Path, bool]]:
    """Parse hierarchical tree representation and resolve each path against root_dir."""
    lines = tree_text.strip().splitlines()
    stack = [root_dir]
    resolved: list[tuple[Path, bool]] = []

    for line in lines:
        line = line.split("#")[0].rstrip()
        if not line or line.strip() == "marketing-campaign-agent/":
            continue

        m = re.search(r"(├── |└── )", line)
        if not m:
            continue

        indent_len = m.start()
        depth = indent_len // 4 + 1
        name = line[m.end() :].strip()
        is_dir = name.endswith("/")
        clean_name = name.rstrip("/")

        stack = stack[:depth]
        target_path = stack[-1] / clean_name
        resolved.append((target_path, is_dir))

        if is_dir:
            stack.append(target_path)

    return resolved


def test_readme_tree_paths_exist() -> None:
    """Every path mentioned in the README repository tree must exist on disk."""
    repo_root = Path(__file__).resolve().parent.parent
    readme_path = repo_root / "README.md"
    assert readme_path.is_file(), f"README.md not found at {readme_path}"

    tree_text = extract_tree_block(readme_path)
    paths = parse_tree_paths(tree_text, repo_root)

    assert len(paths) > 10, f"Expected more than 10 tree items, found {len(paths)}"

    missing_paths = [path for path, _ in paths if not path.exists()]
    assert not missing_paths, (
        "The following paths in README.md repository tree do not exist on disk:\n"
        + "\n".join(str(p.relative_to(repo_root)) for p in missing_paths)
    )
