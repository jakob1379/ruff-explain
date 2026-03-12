from dataclasses import dataclass, field
from http.client import HTTPSConnection
from html.parser import HTMLParser
import re
from typing import Callable
from urllib.parse import ParseResult, urlparse

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .errors import RulePageError
from .rules import normalize_rule_id, require_rule

_WHITESPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"^(?P<name>.+?)\s+\((?P<code>[A-Z]+\d+)\)$")
_FIX_STYLES = {
    "Always": "bold green",
    "Sometimes": "bold yellow",
    "None": "bold red",
}
_DOCS_HOST = "docs.astral.sh"
_DOCS_PATH_PREFIX = "/ruff/rules/"


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    children: list[HtmlNode | str] = field(default_factory=list)


@dataclass
class ParagraphBlock:
    text: str


@dataclass
class ListBlock:
    items: list[str]


@dataclass
class CodeBlock:
    code: str


@dataclass
class Section:
    title: str
    blocks: list[ParagraphBlock | ListBlock | CodeBlock] = field(default_factory=list)


@dataclass
class RulePage:
    name: str
    code: str
    linter: str
    status: str
    since: str
    fix: str
    url: str
    intro_blocks: list[ParagraphBlock | ListBlock | CodeBlock]
    sections: list[Section]


class _DomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


def fetch_rule_page(url: str) -> str:
    parsed = _validate_rule_url(url)
    connection = HTTPSConnection(_DOCS_HOST, timeout=15)
    try:
        connection.request("GET", parsed.path, headers={"User-Agent": "ruff-explain"})
        with connection.getresponse() as response:
            if response.status >= 400:
                raise RulePageError(
                    f"Could not fetch {url}: HTTP {response.status} {response.reason}"
                )
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except OSError as exc:
        raise RulePageError(f"Could not fetch {url}: {exc}") from exc
    finally:
        connection.close()


def _validate_rule_url(url: str) -> ParseResult:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != _DOCS_HOST:
        raise RulePageError(f"Unsupported Ruff docs URL: {url}")
    if not parsed.path.startswith(_DOCS_PATH_PREFIX):
        raise RulePageError(f"Unsupported Ruff docs URL: {url}")
    return parsed


def build_rule_renderable(
    rule_id: str, url: str, html: str | None = None, width: int = 80
) -> RenderableType:
    normalized = rule_id.strip().upper()
    document = parse_rule_page(normalized, url, html or fetch_rule_page(url))

    renderables: list[RenderableType] = [_render_header_panel(document)]
    for section in document.sections:
        renderables.append(_render_section(section, width))
    return Group(*renderables)


def parse_rule_page(rule_id: str, url: str, html: str) -> RulePage:
    normalized = normalize_rule_id(rule_id)
    rule = require_rule(normalized)

    parser = _DomParser()
    parser.feed(html)
    article = _find_first(
        parser.root,
        lambda node: node.tag == "article" and _has_class(node, "md-content__inner"),
    )
    if article is None:
        raise RulePageError("Could not find the Ruff article content in the page.")

    title = _extract_title(article) or f"{rule.slug} ({normalized})"
    match = _TITLE_RE.match(title)
    name = match.group("name") if match else title
    code = match.group("code") if match else normalized

    sections = _extract_sections(article)
    intro_blocks: list[ParagraphBlock | ListBlock | CodeBlock] = []
    if sections and sections[0].title == "Overview":
        intro_blocks = sections.pop(0).blocks

    return RulePage(
        name=name,
        code=code,
        linter=rule.linter,
        status=rule.status,
        since=rule.since,
        fix=rule.fix,
        url=url,
        intro_blocks=intro_blocks,
        sections=sections,
    )


def _extract_title(article: HtmlNode) -> str | None:
    heading = _first_child(article, "h1")
    if heading is None:
        return None
    title = _collapse(_inline_text(heading))
    return title or None


def _extract_sections(article: HtmlNode) -> list[Section]:
    sections: list[Section] = []
    current = Section("Overview")
    saw_content = False

    for node in _iter_article_nodes(article):
        if _should_skip_article_node(node):
            continue

        heading_title = _heading_from_article_node(node)
        if heading_title is not None:
            if current.blocks:
                sections.append(current)
            current = Section(heading_title)
            saw_content = True
            continue

        block = _extract_block(node)
        if block is None:
            continue

        if not saw_content and not current.blocks:
            current = Section("Overview")
        current.blocks.append(block)

    if current.blocks:
        sections.append(current)

    return sections


def _extract_block(node: HtmlNode) -> ParagraphBlock | ListBlock | CodeBlock | None:
    if node.tag == "p":
        return _paragraph_block(node)
    if node.tag in {"ul", "ol"}:
        return _list_block(node)
    if _is_code_node(node):
        return _code_block(node)
    return None


def _iter_article_nodes(article: HtmlNode) -> list[HtmlNode]:
    nodes: list[HtmlNode] = []
    for child in article.children:
        if isinstance(child, HtmlNode):
            nodes.append(child)
    return nodes


def _heading_from_article_node(node: HtmlNode) -> str | None:
    if node.tag in {"h2", "h3"}:
        return _collapse(_inline_text(node))
    return None


def _should_skip_article_node(node: HtmlNode) -> bool:
    return node.tag == "h1" or (node.tag == "p" and _contains_tag(node, "small"))


def _paragraph_block(node: HtmlNode) -> ParagraphBlock | None:
    text = _collapse(_inline_text(node))
    return ParagraphBlock(text) if text else None


def _list_block(node: HtmlNode) -> ListBlock | None:
    items: list[str] = []
    for child in node.children:
        if not isinstance(child, HtmlNode):
            continue
        if child.tag != "li":
            continue
        text = _collapse(_inline_text(child))
        if not text:
            continue
        items.append(text)
    return ListBlock(items) if items else None


def _is_code_node(node: HtmlNode) -> bool:
    return node.tag == "pre" or (node.tag == "div" and _has_class(node, "highlight"))


def _code_block(node: HtmlNode) -> CodeBlock | None:
    code = _extract_code(node)
    return CodeBlock(code) if code else None


def _extract_code(node: HtmlNode) -> str:
    code_node = _find_first(node, lambda child: child.tag == "code")
    source = code_node or node
    code = _node_text(source)
    lines = [line.rstrip() for line in code.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _render_header_panel(page: RulePage) -> Panel:
    title = Text(page.name)
    title.append(f" ({page.code})")
    title.stylize(f"link {page.url}")
    title.stylize("underline cyan")

    header = Text()
    header.append("Linter: ", style="bold")
    header.append(page.linter)
    header.append(" - ")
    header.append("Status: ", style="bold")
    header.append(page.status)
    header.append(" - ")
    header.append("Added: ", style="bold")
    header.append(page.since)
    header.append(" - ")
    header.append("Fix: ", style="bold")
    header.append(page.fix, style=_FIX_STYLES.get(page.fix, "bold"))
    header.justify = "center"

    body_renderables: list[RenderableType] = [header]
    intro = _render_blocks(page.intro_blocks)
    if intro is not None:
        body_renderables.append(Text())
        body_renderables.append(intro)

    return Panel(
        Group(*body_renderables),
        title=title,
        border_style="cyan",
        padding=(0, 1),
    )


def _render_section(section: Section, width: int) -> RenderableType:
    if section.title.casefold() == "example":
        return _render_example_section(section, width)

    body = _render_blocks(section.blocks)
    return Panel(
        body or Text(),
        title=section.title,
        border_style="blue",
        padding=(0, 1),
    )


def _render_example_section(section: Section, width: int) -> RenderableType:
    example_blocks: list[ParagraphBlock | ListBlock | CodeBlock] = []
    preferred_blocks: list[ParagraphBlock | ListBlock | CodeBlock] = []
    target = example_blocks

    for block in section.blocks:
        if isinstance(block, ParagraphBlock) and block.text.casefold().startswith(
            "use instead"
        ):
            target = preferred_blocks
            continue
        target.append(block)

    example_panel = Panel(
        _render_blocks(example_blocks) or Text(),
        title="Example: Python",
        border_style="yellow",
        padding=(0, 1),
    )
    if not preferred_blocks:
        return example_panel

    preferred_panel = Panel(
        _render_blocks(preferred_blocks) or Text(),
        title="Use instead: Python",
        border_style="green",
        padding=(0, 1),
    )
    if width >= 120:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(ratio=1)
        table.add_column(ratio=1)
        table.add_row(example_panel, preferred_panel)
        return table
    return Group(example_panel, preferred_panel)


def _render_blocks(
    blocks: list[ParagraphBlock | ListBlock | CodeBlock],
) -> RenderableType | None:
    if not blocks:
        return None
    renderables: list[RenderableType] = []
    for block in blocks:
        if isinstance(block, ParagraphBlock):
            renderables.append(Text(block.text))
        elif isinstance(block, ListBlock):
            renderables.extend(Text(f"- {item}") for item in block.items)
        else:
            renderables.append(
                Syntax(block.code, "python", line_numbers=False, word_wrap=False)
            )
    spaced: list[RenderableType] = []
    for index, renderable in enumerate(renderables):
        if index:
            spaced.append(Text())
        spaced.append(renderable)
    return Group(*spaced)


def _first_child(node: HtmlNode, tag: str) -> HtmlNode | None:
    for child in node.children:
        if isinstance(child, HtmlNode) and child.tag == tag:
            return child
    return None


def _find_first(
    node: HtmlNode, predicate: Callable[[HtmlNode], bool]
) -> HtmlNode | None:
    if predicate(node):
        return node
    for child in node.children:
        if isinstance(child, HtmlNode):
            found = _find_first(child, predicate)
            if found is not None:
                return found
    return None


def _has_class(node: HtmlNode, class_name: str) -> bool:
    return class_name in node.attrs.get("class", "").split()


def _contains_tag(node: HtmlNode, tag: str) -> bool:
    return _find_first(node, lambda child: child.tag == tag) is not None


def _node_text(node: HtmlNode | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return "\n"
    return "".join(_node_text(child) for child in node.children)


def _inline_text(node: HtmlNode | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return "\n"
    if node.tag == "code":
        return f"`{_collapse(_node_text(node))}`"
    return "".join(_inline_text(child) for child in node.children)


def _collapse(text: str) -> str:
    parts = [
        _WHITESPACE_RE.sub(" ", line).strip()
        for line in text.replace("\xa0", " ").splitlines()
    ]
    return " ".join(part for part in parts if part).strip()
