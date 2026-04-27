from difflib import get_close_matches
from importlib.metadata import PackageNotFoundError, version
import json
import webbrowser

import typer
from rich.console import Console

from .errors import RulePageError, UnknownRuleError
from .render import (
    CodeBlock,
    ListBlock,
    ParagraphBlock,
    RulePage,
    build_rule_renderable,
    fetch_rule_page,
    parse_rule_page,
)
from .rules import RuleRecord, build_rule_url, normalize_rule_id, require_rule, rule_ids

app = typer.Typer(
    add_completion=False, help="Look up Ruff rule documentation by rule ID."
)
console = Console()
error_console = Console(stderr=True)


def _unknown_rule_details(rule_id: str) -> tuple[str, list[str]]:
    normalized = normalize_rule_id(rule_id)
    matches = get_close_matches(normalized, rule_ids(), n=3, cutoff=0.6)
    return normalized, matches


def _unknown_rule(rule_id: str) -> None:
    normalized, matches = _unknown_rule_details(rule_id)
    error_console.print(f"[bold red]Unknown Ruff rule:[/bold red] {normalized}")
    if matches:
        error_console.print(f"Did you mean: {', '.join(matches)}")
    raise typer.Exit(code=1)


def _emit_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _serialize_block(
    block: ParagraphBlock | ListBlock | CodeBlock,
) -> dict[str, str | list[str]]:
    if isinstance(block, ParagraphBlock):
        return {"type": "paragraph", "text": block.text}
    if isinstance(block, ListBlock):
        return {"type": "list", "items": block.items}
    return {"type": "code", "code": block.code}


def _serialize_page(page: RulePage, rule: RuleRecord) -> dict[str, object]:
    return {
        "code": page.code,
        "slug": rule.slug,
        "summary": rule.summary,
        "title": page.name,
        "linter": page.linter,
        "status": page.status,
        "since": page.since,
        "fix": page.fix,
        "url": page.url,
        "overview": [_serialize_block(block) for block in page.intro_blocks],
        "sections": [
            {
                "title": section.title,
                "blocks": [_serialize_block(block) for block in section.blocks],
            }
            for section in page.sections
        ],
    }


def _json_error(
    error_type: str,
    message: str,
    **details: str | list[str],
) -> None:
    _emit_json({"error": {"type": error_type, "message": message, **details}})


def _version_callback(value: bool) -> None:
    if not value:
        return

    try:
        package_version = version("ruff-explain")
    except PackageNotFoundError:
        package_version = "unknown"

    typer.echo(f"ruff-explain {package_version}")
    raise typer.Exit()


@app.command()
def lookup(
    rule_id: str = typer.Argument(..., help="Ruff rule ID, for example FAST001."),
    show_version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
    open_page: bool = typer.Option(
        False, "--open", "-o", help="Open the docs page in your browser."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print structured JSON instead of Rich output."
    ),
) -> None:
    normalized = normalize_rule_id(rule_id)

    if open_page and json_output:
        _json_error(
            "invalid_options",
            "--json cannot be combined with --open.",
            rule_id=normalized,
        )
        raise typer.Exit(code=1)

    try:
        rule = require_rule(normalized)
    except UnknownRuleError:
        if json_output:
            unknown_rule, matches = _unknown_rule_details(rule_id)
            _json_error(
                "unknown_rule",
                f"Unknown Ruff rule: {unknown_rule}",
                rule_id=unknown_rule,
                suggestions=matches,
            )
            raise typer.Exit(code=1)
        _unknown_rule(rule_id)
        return

    url = build_rule_url(rule)

    if open_page:
        webbrowser.open_new_tab(url)
        return

    if json_output:
        try:
            html = fetch_rule_page(url)
        except RulePageError as exc:
            _json_error(
                "fetch_failed",
                str(exc),
                rule_id=normalized,
                url=url,
            )
            raise typer.Exit(code=1) from exc

        try:
            _emit_json(_serialize_page(parse_rule_page(normalized, url, html), rule))
        except RulePageError as exc:
            _json_error(
                "parse_failed",
                str(exc),
                rule_id=normalized,
                url=url,
            )
            raise typer.Exit(code=1) from exc
        return

    try:
        console.print(build_rule_renderable(normalized, url, width=console.size.width))
    except RulePageError as exc:
        error_console.print(f"[bold red]Render failed:[/bold red] {exc}")
        console.print(f"[bold]{normalized}[/bold]")
        console.print(f"[link={url}]{url}[/link]")
        raise typer.Exit(code=1) from exc


def main() -> None:
    app()
