from __future__ import annotations

import pytest

from ruff_explain.errors import UnknownRuleError
from ruff_explain.rules import all_rules, get_rule, get_rule_url, require_rule, rule_ids


def test_get_rule_returns_typed_record() -> None:
    rule = get_rule("fast001")

    assert rule is not None
    assert rule.slug == "fast-api-redundant-response-model"
    assert get_rule_url("FAST001") == (
        "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/"
    )


def test_all_rules_have_complete_metadata() -> None:
    rules = all_rules()

    assert rules
    for rule_id, rule in rules.items():
        assert rule_id == rule_id.upper()
        assert rule.slug
        assert rule.linter
        assert rule.fix
        assert rule.status
        assert rule.since


def test_require_rule_raises_for_unknown_rule_id() -> None:
    with pytest.raises(UnknownRuleError, match="Unknown Ruff rule: NOPE999"):
        require_rule("NOPE999")


def test_rule_ids_include_known_rules() -> None:
    ids = rule_ids()

    assert "FAST001" in ids
    assert "F401" in ids
