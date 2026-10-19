"""Input sanitisation and prompt injection detection."""

from __future__ import annotations

import re

from campaign.models import ProductBrief


class HostileInputError(ValueError):
    """Raised when an input contains suspected adversarial prompt injection."""


# Control characters excluding normal whitespace (\t, \n, \r)
# Also strip zero-width characters (\u200b, \u200c, \u200d, \ufeff)
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b\u200c\u200d\ufeff]")

_INJECTION_PATTERNS = [
    re.compile(
        r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)?\s*(?:instructions|prompts|rules|commands)",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(?:all\s+)?(?:previous|prior|above)?\s*(?:instructions|prompts|commands|rules|demographic)",
        re.IGNORECASE,
    ),
    re.compile(r"system\s+(?:override|alert|prompt|instruction|advisory)", re.IGNORECASE),
    re.compile(r"developer\s+mode", re.IGNORECASE),
    re.compile(r"you\s+are\s+now", re.IGNORECASE),
    re.compile(r"forget\s+(?:everything|safety|constraints|demographics)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:guardrails|filters|security)", re.IGNORECASE),
    re.compile(r"new\s+instructions:", re.IGNORECASE),
    re.compile(r"instruction\s+injection", re.IGNORECASE),
    re.compile(r"prompt\s+override", re.IGNORECASE),
    re.compile(r"output\s+['\"]?(?:all_data_leaked|hacked)['\"]?", re.IGNORECASE),
    re.compile(r"(?:delete|reveal)\s+(?:your\s+)?instructions", re.IGNORECASE),
]


def sanitize_text(text: str, max_length: int = 2000) -> str:
    """Strip control and zero-width characters and cap maximum length."""
    sanitized = _CONTROL_CHAR_REGEX.sub("", text)
    return sanitized[:max_length]


def detect_prompt_injection(text: str) -> bool:
    """Return True if text matches known prompt injection signatures."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def wrap_untrusted(text: str) -> str:
    """Neutralize internal untrusted tags and wrap text in <untrusted> boundaries."""
    neutralized = text.replace("<untrusted>", "&lt;untrusted&gt;").replace(
        "</untrusted>", "&lt;/untrusted&gt;"
    )
    return f"<untrusted>{neutralized}</untrusted>"


def sanitize_brief(brief: ProductBrief) -> ProductBrief:
    """Sanitize product brief fields and fail-closed if prompt injection is detected."""
    clean_name = sanitize_text(brief.name, max_length=80)
    clean_desc = sanitize_text(brief.description, max_length=2000)

    if detect_prompt_injection(clean_name) or detect_prompt_injection(clean_desc):
        raise HostileInputError("Product brief contains suspected prompt injection patterns")

    return ProductBrief(
        name=clean_name,
        description=clean_desc,
        segment=brief.segment,
        budget_usd=brief.budget_usd,
    )
