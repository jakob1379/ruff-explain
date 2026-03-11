from __future__ import annotations

from difflib import get_close_matches
import webbrowser

import typer
from rich.console import Console

from .render import RulePageError, build_rule_renderable
from .rules import BASE_URL, RULES

app = typer.Typer(
    add_completion=False, help="Look up Ruff rule documentation by rule ID."
)
console = Console()
error_console = Console(stderr=True)


def _rule_url(rule_id: str) -> str | None:
    rule = RULES.get(rule_id.strip().upper())
    if rule is None:
        return None
    return f"{BASE_URL}{rule['slug']}/"


def _unknown_rule(rule_id: str) -> None:
    normalized = rule_id.strip().upper()
    matches = get_close_matches(normalized, RULES, n=3, cutoff=0.6)
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
    url = _rule_url(rule_id)
    if url is None:
        _unknown_rule(rule_id)

    if open_page:
        webbrowser.open_new_tab(url)
        return

    normalized = rule_id.strip().upper()
    try:
        console.print(build_rule_renderable(normalized, url, width=console.size.width))
    except RulePageError as exc:
        error_console.print(f"[bold red]Render failed:[/bold red] {exc}")
        console.print(f"[bold]{normalized}[/bold]")
        console.print(f"[link={url}]{url}[/link]")
        raise typer.Exit(code=1) from exc


def main() -> None:
    app()
