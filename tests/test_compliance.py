"""Tests for advertising copy compliance checks (Tests First)."""

import pytest

from campaign.compliance import check_copy_compliance

BANNED_PHRASES = [
    "guaranteed",
    "100% safe",
    "cure",
    "miracle",
    "risk-free",
    "#1 in the world",
]


@pytest.mark.parametrize("phrase", BANNED_PHRASES)
def test_banned_phrases_detected(phrase):
    text = f"Our new bottle offers a {phrase} experience."
    violations = check_copy_compliance(text)
    assert len(violations) > 0
    assert any(phrase.lower() in v.lower() for v in violations)


def test_word_boundaries_do_not_trigger_false_positives():
    # 'secure' contains 'cure' as substring, but is not the banned word 'cure'
    # 'accurate' contains 'cure'
    # 'miraculous' contains 'miracle' but let's test strict word boundaries
    text = "A secure container with accurate temperature tracking."
    violations = check_copy_compliance(text)
    assert violations == []


def test_percent_off_rule_unauthorized():
    # Digit followed by % off without brief mention
    text = "Get yours now for 50% off retail price!"
    violations = check_copy_compliance(text, brief_text="Standard retail launch.")
    assert len(violations) == 1
    assert "percent off" in violations[0].lower() or "% off" in violations[0].lower()

    # With space
    text2 = "Limited time: 20 % off today."
    violations2 = check_copy_compliance(text2, brief_text="Standard retail launch.")
    assert len(violations2) == 1


def test_percent_off_rule_authorized_by_brief():
    # When brief mentions the discount, it is permitted
    brief = "Special promotional campaign offering 50% off for early adopters."
    text = "Claim your 50% off early bird discount today!"
    violations = check_copy_compliance(text, brief_text=brief)
    assert violations == []


def test_clean_copy_passes_compliance():
    text = "Brightside EcoBottle keeps your drinks cold for 24 hours. Built for active commuters."
    violations = check_copy_compliance(text, brief_text="A stainless steel bottle.")
    assert violations == []
