"""Small presentation hooks for the custom documentation theme."""

from html import escape
from pathlib import Path
import re

from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound


class CodeBlockFormatter(HtmlFormatter):
    """Keep code metadata and controls outside the copyable source."""

    def __init__(self, lang_str="language-text", **options):
        options["linenos"] = False  # Keep line-number markup out of the copyable source.
        super().__init__(**options)
        language = lang_str.removeprefix("language-")
        self.language = language if re.fullmatch(r"[\w.+#-]+", language) else "text"
        self.code_filename = self.filename
        self.filename = ""
        self.plain_text = self.language in {"text", "txt", "plaintext"}
        self.preserve_lines = self.language in {
            "text", "txt", "plaintext", "console", "shell-session", "pycon",
        }
        self.flow_text = self.preserve_lines and options.get("layout") == "flow"
        self.compact_output = self.plain_text or self.flow_text
        self.text_title = str(options.get("title", "")) if self.compact_output else ""
        try:
            self.language_label = get_lexer_by_name(self.language).name
        except ClassNotFound:
            self.language_label = "Text"
        if self.language in {"text", "txt", "plaintext"}:
            self.language_label = "Text"
        elif self.language in {"console", "shell-session"}:
            self.language_label = "Terminal"

    def wrap(self, source):
        filename = escape(self.code_filename)
        language = escape(self.language, quote=True)
        label = escape(self.language_label)
        kind = "block" if self.preserve_lines else "source code"
        region = escape(f"{self.text_title or self.code_filename or self.language_label} {kind}", quote=True)
        if self.compact_output:
            if filename:
                yield 0, f'<div class="text-caption"><span class="code-filename">{filename}</span></div>'
            yield 0, '<div class="code-actions"></div>'
        else:
            yield 0, '<div class="code-toolbar"><div class="code-label">'
            if filename:
                yield 0, f'<span class="code-filename">{filename}</span>'
            yield 0, f'<span class="code-language">{label}</span>'
            if self.preserve_lines:
                yield 0, '<span class="code-scroll-hint" hidden aria-hidden="true">Scroll horizontally &rarr;</span>'
            yield 0, '</div><div class="code-actions"></div></div>'
        yield 0, f'<pre tabindex="0" role="group" aria-label="{region}"><code class="language-{language}">'
        for kind, line in source:
            if self.plain_text and self.flow_text:
                line = re.sub(r"\b0x[0-9a-fA-F]{16,}\b", r'<span class="text-value">\g<0></span>', line)
            yield kind, line
        yield 0, '</code></pre>'
        if self.compact_output or not self.preserve_lines:
            yield 0, '<div class="code-scroll-hint" hidden aria-hidden="true">Scroll horizontally to read &rarr;</div>'

    def _wrap_div(self, inner):
        classes = escape(f"{self.cssclass} code-block{' text-block' if self.compact_output else ''}", quote=True)
        language = escape(self.language, quote=True)
        wrap = "flow" if self.flow_text else "preserve" if self.preserve_lines else "auto"
        yield 0, f'<div class="{classes}" data-language="{language}" data-wrap="{wrap}">'
        yield from inner
        yield 0, '</div>\n'


def on_config(config):
    config["mdx_configs"].setdefault("codehilite", {})["pygments_formatter"] = CodeBlockFormatter
    return config


def on_page_markdown(markdown, page, config, files):
    """Expose source Markdown for Copy page without exposing front matter."""
    source = Path(page.file.src_uri).with_suffix(".md").as_posix()
    page.meta["markdown_url"] = f"_sources/{source}"
    page.meta["source_markdown"] = markdown
    return markdown


def on_page_content(html, page, config, files):
    """The theme supplies the H1; keep wide tables inside their own scroller."""
    html = re.sub(r"^\s*<h1\b[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.S)
    return re.sub(
        r"(<table\b.*?</table>)",
        lambda match: (
            '<div class="table-scroll" role="region" tabindex="0" '
            f'aria-label="{escape(page.title, quote=True)} table">{match[1]}</div>'
        ),
        html,
        flags=re.S,
    )


def on_post_page(output, page, config):
    """Ship a plain Markdown copy of each page for clipboard controls."""
    destination = Path(config["site_dir"]) / page.meta["markdown_url"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(page.meta["source_markdown"], encoding="utf-8")
    return output
