"""Small presentation hooks for the custom documentation theme."""

from html import escape
from pathlib import Path
import re


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
