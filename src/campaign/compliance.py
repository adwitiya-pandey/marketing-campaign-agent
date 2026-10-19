"""Advertising copy compliance checks."""

from __future__ import annotations

import re

# Banned phrases that violate advertising standards
BANNED_RULES = [
    (re.compile(r"\bguaranteed\b", re.IGNORECASE), "Banned claim: 'guaranteed'"),
    (re.compile(r"\b100%\s*safe\b", re.IGNORECASE), "Banned claim: '100% safe'"),
    (re.compile(r"\bcure\b", re.IGNORECASE), "Banned claim: 'cure'"),
    (re.compile(r"\bmiracle\b", re.IGNORECASE), "Banned claim: 'miracle'"),
    (re.compile(r"\brisk[- ]free\b", re.IGNORECASE), "Banned claim: 'risk-free'"),
    (re.compile(r"#1\s+in\s+the\s+world", re.IGNORECASE), "Banned claim: '#1 in the world'"),
]

_PERCENT_OFF_REGEX = re.compile(r"\b([0-9]{1,3})\s*%\s*off\b", re.IGNORECASE)


def check_copy_compliance(text: str, brief_text: str = "") -> list[str]:
    """Check text against banned advertising phrases and unapproved discount claims."""
    violations: list[str] = []

    # 1. Check banned phrases with word boundary protection
    for pattern, message in BANNED_RULES:
        if pattern.search(text):
            violations.append(message)

    # 2. Check '% off' claims: prohibited unless brief explicitly mentions the discount
    for match in _PERCENT_OFF_REGEX.finditer(text):
        discount_claim = match.group(0)
        percentage = match.group(1)
        # Check if brief contains this percentage or percentage off
        if f"{percentage}%" not in brief_text and f"{percentage} %" not in brief_text:
            violations.append(
                f"Unauthorized discount claim '{discount_claim}' not mentioned in product brief"
            )

    return violations
