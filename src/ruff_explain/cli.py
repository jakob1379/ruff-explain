from difflib import get_close_matches
import webbrowser

import typer
from rich.console import Console

from .errors import RulePageError, UnknownRuleError
from .render import build_rule_renderable
from .rules import build_rule_url, normalize_rule_id, require_rule, rule_ids

app = typer.Typer(
    add_completion=False, help="Look up Ruff rule documentation by rule ID."
)
console = Console()
error_console = Console(stderr=True)


def _unknown_rule(rule_id: str) -> None:
    normalized = normalize_rule_id(rule_id)
    matches = get_close_matches(normalized, rule_ids(), n=3, cutoff=0.6)
    error_console.print(f"[bold red]Unknown Ruff rule:[/bold red] {normalized}")
    if matches:
        error_console.print(f"Did you mean: {', '.join(matches)}")
    raise typer.Exit(code=1)


@app.command()
def lookup(
    rule_id: str = typer.Argument(..., help="Ruff rule ID, for example FAST001."),
    open_page: bool = typer.Option(
        False, "--open", "-o", help="Open the docs page in your browser."
    ),
) -> None:
    normalized = normalize_rule_id(rule_id)
    try:
        rule = require_rule(normalized)
    except UnknownRuleError:
        _unknown_rule(rule_id)
        return

    url = build_rule_url(rule)

    if open_page:
        webbrowser.open_new_tab(url)
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
