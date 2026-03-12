from __future__ import annotations

from ruff_explain.errors import UnknownRuleError


def test_unknown_rule_error_preserves_rule_id() -> None:
    error = UnknownRuleError("NOPE999")

    assert error.rule_id == "NOPE999"
    assert str(error) == "Unknown Ruff rule: NOPE999"
