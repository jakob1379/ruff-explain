from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.resources import files
import json

from .errors import UnknownRuleError
from .rule_data import GROUPS

BASE_URL = "https://docs.astral.sh/ruff/rules/"


@dataclass(frozen=True, slots=True)
class RuleRecord:
    slug: str
    linter: str
    summary: str
    fix: str
    status: str
    since: str


def normalize_rule_id(rule_id: str) -> str:
    return rule_id.strip().upper()


def build_rule_url(rule: RuleRecord) -> str:
    return f"{BASE_URL}{rule.slug}/"


def get_rule_url(rule_id: str) -> str | None:
    rule = get_rule(rule_id)
    if rule is None:
        return None
    return build_rule_url(rule)


def get_rule(rule_id: str) -> RuleRecord | None:
    normalized = normalize_rule_id(rule_id)
    if not normalized:
        return None
    return _load_group(normalized[0].lower()).get(normalized)


def require_rule(rule_id: str) -> RuleRecord:
    normalized = normalize_rule_id(rule_id)
    rule = get_rule(normalized)
    if rule is None:
        raise UnknownRuleError(normalized)
    return rule


def rule_ids() -> tuple[str, ...]:
    return tuple(all_rules())


@cache
def all_rules() -> dict[str, RuleRecord]:
    rules: dict[str, RuleRecord] = {}
    for group in GROUPS:
        rules.update(_load_group(group))
    return rules


@cache
def _load_group(group: str) -> dict[str, RuleRecord]:
    if group not in GROUPS:
        return {}
    data_path = files("ruff_explain.rule_data") / f"{group}.json"
    records = json.loads(data_path.read_text(encoding="utf-8"))
    return {rule_id: RuleRecord(**record) for rule_id, record in records.items()}


__all__ = [
    "BASE_URL",
    "RuleRecord",
    "all_rules",
    "build_rule_url",
    "get_rule",
    "get_rule_url",
    "normalize_rule_id",
    "require_rule",
    "rule_ids",
]
