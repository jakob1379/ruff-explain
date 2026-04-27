import json

from typer.testing import CliRunner

from ruff_explain import cli


runner = CliRunner()


def test_fast001_renders_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "build_rule_renderable",
        lambda rule_id, url, width: f"rendered {rule_id} {url}",
    )

    result = runner.invoke(cli.app, ["FAST001"])

    assert result.exit_code == 0
    assert "rendered FAST001" in result.stdout
    assert "fast-api-redundant-response-model" in result.stdout


def test_fast001_open_skips_render_and_opens_browser(monkeypatch) -> None:
    opened: list[str] = []

    def fail_render(*_args, **_kwargs):
        raise AssertionError("render should not be called when --open is used")

    monkeypatch.setattr(cli, "build_rule_renderable", fail_render)
    monkeypatch.setattr(cli.webbrowser, "open_new_tab", opened.append)

    result = runner.invoke(cli.app, ["FAST001", "--open"])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert opened == [
        "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/"
    ]


def test_version_flag_prints_version_and_exits(monkeypatch) -> None:
    monkeypatch.setattr(cli, "version", lambda _package: "1.0.1")

    long_result = runner.invoke(cli.app, ["--version"])
    short_result = runner.invoke(cli.app, ["-v"])

    assert long_result.exit_code == 0
    assert long_result.stdout == "ruff-explain 1.0.1\n"
    assert short_result.exit_code == 0
    assert short_result.stdout == "ruff-explain 1.0.1\n"


def test_fast001_json_outputs_machine_readable_rule(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "fetch_rule_page",
        lambda _url: """
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
        """,
    )

    result = runner.invoke(cli.app, ["FAST001", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["code"] == "FAST001"
    assert payload["slug"] == "fast-api-redundant-response-model"
    assert payload["summary"] == "FastAPI route with redundant `response_model` argument"
    assert payload["title"] == "Fast API redundant response model"
    assert payload["url"].endswith("fast-api-redundant-response-model/")
    assert payload["overview"] == [
        {"type": "paragraph", "text": "Overview paragraph."}
    ]
    assert payload["sections"] == [
        {
            "title": "Why is this bad?",
            "blocks": [
                {
                    "type": "paragraph",
                    "text": "Because the response model is already inferred.",
                }
            ],
        },
        {
            "title": "Example",
            "blocks": [
                {"type": "code", "code": "bad()"},
                {"type": "paragraph", "text": "Use instead:"},
                {"type": "code", "code": "good()"},
            ],
        },
    ]


def test_json_and_open_are_mutually_exclusive() -> None:
    result = runner.invoke(cli.app, ["FAST001", "--json", "--open"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": {
            "type": "invalid_options",
            "message": "--json cannot be combined with --open.",
            "rule_id": "FAST001",
        }
    }


def test_unknown_rule_json_is_machine_readable() -> None:
    result = runner.invoke(cli.app, ["NOPE999", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["type"] == "unknown_rule"
    assert payload["error"]["rule_id"] == "NOPE999"
    assert payload["error"]["message"] == "Unknown Ruff rule: NOPE999"
    assert isinstance(payload["error"]["suggestions"], list)


def test_json_fetch_failures_are_machine_readable(monkeypatch) -> None:
    def fail_fetch(_url: str) -> str:
        raise cli.RulePageError("boom")

    monkeypatch.setattr(cli, "fetch_rule_page", fail_fetch)

    result = runner.invoke(cli.app, ["FAST001", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": {
            "type": "fetch_failed",
            "message": "boom",
            "rule_id": "FAST001",
            "url": "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/",
        }
    }


def test_json_parse_failures_are_machine_readable(monkeypatch) -> None:
    monkeypatch.setattr(cli, "fetch_rule_page", lambda _url: "<html></html>")

    result = runner.invoke(cli.app, ["FAST001", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": {
            "type": "parse_failed",
            "message": "Could not find the Ruff article content in the page.",
            "rule_id": "FAST001",
            "url": "https://docs.astral.sh/ruff/rules/fast-api-redundant-response-model/",
        }
    }
