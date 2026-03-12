class RuffExplainError(Exception):
    pass


class UnknownRuleError(RuffExplainError):
    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"Unknown Ruff rule: {rule_id}")


class RulePageError(RuffExplainError):
    pass
