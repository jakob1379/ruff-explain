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
