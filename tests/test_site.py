"""Validate built documentation, including deployment under a project prefix."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BASE_URL = "https://evilzcoder.github.io/kokogray-lab/"


class Page(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.ids = []
        self.refs = []
        self.h1_count = 0
        self.main_count = 0
        self.title_count = 0
        self.images_without_alt = []
        self.body = {}
        self.feed(content)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.refs.append((tag, attrs[key]))
        self.h1_count += tag == "h1"
        self.main_count += tag == "main"
        self.title_count += tag == "title"
        if tag == "img" and "alt" not in attrs:
            self.images_without_alt.append(attrs)
        if tag == "body":
            self.body = attrs


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert (SITE / "index.html").is_file(), "Run mkdocs build --strict before testing"
        cls.pages = {
            path: Page(path.read_text(encoding="utf-8"))
            for path in SITE.rglob("*.html")
        }

    def test_semantic_page_shell(self):
        for path, page in self.pages.items():
            with self.subTest(page=path.relative_to(SITE)):
                self.assertEqual(page.h1_count, 1)
                self.assertEqual(page.main_count, 1)
                self.assertEqual(page.title_count, 1)
                self.assertEqual(len(page.ids), len(set(page.ids)), "Duplicate HTML ids")
                self.assertFalse(page.images_without_alt)

    def test_local_links_assets_and_anchors(self):
        for path, page in self.pages.items():
            relative = path.relative_to(SITE).as_posix()
            page_url = urljoin(BASE_URL, relative.removesuffix("index.html"))
            for tag, reference in page.refs:
                parsed = urlsplit(urljoin(page_url, reference))
                if parsed.scheme not in ("http", "https") or parsed.netloc != urlsplit(BASE_URL).netloc:
                    continue
                if not parsed.path.startswith("/kokogray-lab/"):
                    self.fail(f"Link escapes the project prefix: {relative}: {reference}")
                target = SITE / unquote(parsed.path.removeprefix("/kokogray-lab/"))
                if target.is_dir() or parsed.path.endswith("/"):
                    target = target / "index.html"
                with self.subTest(page=relative, reference=reference):
                    self.assertTrue(target.is_file(), f"Missing local target: {target}")
                    if parsed.fragment and target in self.pages:
                        self.assertIn(unquote(parsed.fragment), self.pages[target].ids)

    def test_copy_page_sources(self):
        for path, page in self.pages.items():
            if path.name == "404.html":
                continue
            source = page.body.get("data-markdown-url")
            self.assertTrue(source, f"Missing Markdown source on {path}")
            relative = path.relative_to(SITE).as_posix().removesuffix("index.html")
            url = urlsplit(urljoin(urljoin(BASE_URL, relative), source))
            target = SITE / url.path.removeprefix("/kokogray-lab/")
            self.assertTrue(target.is_file())
            markdown = target.read_text(encoding="utf-8")
            self.assertIn("# ", markdown)
            self.assertFalse(markdown.startswith("---"), "Front matter should not be copied")

    def test_search_index_contains_every_content_page(self):
        index = json.loads((SITE / "search/search_index.json").read_text(encoding="utf-8"))
        locations = {document["location"].split("#")[0] for document in index["docs"]}
        for path in self.pages:
            if path.name == "404.html":
                continue
            relative = path.relative_to(SITE).as_posix().removesuffix("index.html")
            self.assertIn(relative, locations)
        self.assertTrue(any("Cloud security" == doc["title"] for doc in index["docs"]))

    def test_fonts_and_styles_are_local(self):
        css = (SITE / "assets/styles.css").read_text(encoding="utf-8")
        for target in re.findall(r'url\(["\']?([^"\')]+)', css):
            self.assertNotIn("://", target)
            self.assertTrue((SITE / "assets" / target).is_file())
        for name in ("inter", "ibm-plex-mono"):
            self.assertTrue((SITE / "assets/fonts" / f"{name}-OFL.txt").is_file())
        for path in self.pages:
            content = path.read_text(encoding="utf-8")
            self.assertNotRegex(content, r'<(?:script|img)[^>]+src="https?://')

    def test_no_template_leaks_or_credentials(self):
        for path in SITE.rglob("*"):
            if path.suffix not in (".html", ".js", ".css", ".md", ".json"):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}")
            if path.suffix == ".html":
                self.assertNotRegex(text, r"\{%\s*(?:if|for|block|extends)\b")


if __name__ == "__main__":
    unittest.main()
