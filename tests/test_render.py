from __future__ import annotations

import pytest
from rich.console import Console

from ruff_explain.errors import RulePageError, UnknownRuleError
from ruff_explain.render import build_rule_renderable, fetch_rule_page, parse_rule_page


def test_parse_rule_page_rejects_unknown_rule_id() -> None:
    html = "<article class='md-content__inner'><h1>Example (FAST001)</h1></article>"

    with pytest.raises(UnknownRuleError, match="Unknown Ruff rule: NOPE999"):
        parse_rule_page("NOPE999", "https://example.invalid", html)


def test_parse_rule_page_extracts_overview_and_sections() -> None:
    html = """
    <article class="md-content__inner">
      <h1>Fast API redundant response model (FAST001)</h1>
      <p>Overview paragraph.</p>
      <h2>Why is this bad?</h2>
      <p>Because the response model is already inferred.</p>
      <h2>Example</h2>
      <pre><code>bad()</code></pre>
      <p>Use instead:</p>
      <pre><code>good()</code></pre>
    </article>
    """

    page = parse_rule_page(
        "FAST001",
        "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/",
        html,
    )

    assert page.code == "FAST001"
    assert len(page.intro_blocks) == 1
    assert page.intro_blocks[0].text == "Overview paragraph."
    assert [section.title for section in page.sections] == [
        "Why is this bad?",
        "Example",
    ]


def test_build_rule_renderable_renders_sections_from_inline_html() -> None:
    html = """
    <article class="md-content__inner">
      <h1>Fast API redundant response model (FAST001)</h1>
      <p>Overview paragraph.</p>
      <h2>Why is this bad?</h2>
      <p>Because the response model is already inferred.</p>
    </article>
    """

    renderable = build_rule_renderable(
        "FAST001",
        "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/",
        html=html,
        width=100,
    )
    console = Console(record=True, width=100)

    console.print(renderable)

    output = console.export_text()
    assert "Overview paragraph." in output
    assert "Why is this bad?" in output


def test_fetch_rule_page_rejects_untrusted_urls() -> None:
    with pytest.raises(RulePageError, match="Unsupported Ruff docs URL"):
        fetch_rule_page("file:///tmp/rule.html")
