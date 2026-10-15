"""Regression coverage for the documentation code-block presentation hook."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
MAGIC_VAULT = ROOT / "docs" / "introduction-to-blockchain" / "magic-vault.md"
MAGIC_VAULT_HTML = SITE / "introduction-to-blockchain" / "magic-vault" / "index.html"
MAGIC_VAULT_SOURCE = SITE / "_sources" / "introduction-to-blockchain" / "magic-vault.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from markdown import markdown
from pygments import highlight
from pygments.lexers.special import TextLexer
from scripts.hooks import CodeBlockFormatter, on_config


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
FENCE_PATTERN = re.compile(
    r"^```(?P<info>[^\r\n]*)\r?\n(?P<body>.*?)(?=^```[ \t]*$)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
ATTRIBUTE_PATTERN = r"(?:^|\s){name}\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s}}]+))"


@dataclass
class Node:
    """A small, dependency-free representation of the generated HTML."""

    tag: str
    attributes: dict[str, str | None]
    children: list["Node | str"] = field(default_factory=list)

    def descendants(self, tag: str | None = None, class_name: str | None = None):
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and (class_name is None or has_class(child, class_name)):
                yield child
            yield from child.descendants(tag=tag, class_name=class_name)


class Document(HTMLParser):
    """Parse the limited HTML assertions below without adding Beautiful Soup."""

    def __init__(self, content: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]
        self.tags: list[str] = []
        self.feed(content)
        self.close()

    def handle_starttag(self, tag: str, attributes):
        node = Node(tag, dict(attributes))
        self.stack[-1].children.append(node)
        self.tags.append(tag)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attributes):
        node = Node(tag, dict(attributes))
        self.stack[-1].children.append(node)
        self.tags.append(tag)

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str):
        self.stack[-1].children.append(data)


def has_class(node: Node, class_name: str) -> bool:
    return class_name in (node.attributes.get("class") or "").split()


def text_content(node: Node) -> str:
    return "".join(
        child if isinstance(child, str) else text_content(child)
        for child in node.children
    )


def descendants(node: Node, *, tag: str | None = None, class_name: str | None = None) -> list[Node]:
    return list(node.descendants(tag=tag, class_name=class_name))


def only(nodes: list[Node], description: str) -> Node:
    if len(nodes) != 1:
        raise AssertionError(f"Expected one {description}, found {len(nodes)}")
    return nodes[0]


def trim_one_final_newline(value: str) -> str:
    """Permit Markdown/Pygments to differ only by the conventional final newline."""

    return value[:-1] if value.endswith("\n") else value


def render_markdown(source: str) -> str:
    return markdown(
        source,
        extensions=["fenced_code", "codehilite", "attr_list"],
        extension_configs={
            "codehilite": {
                "guess_lang": False,
                "pygments_formatter": CodeBlockFormatter,
            }
        },
    )


@dataclass(frozen=True)
class Fence:
    info: str
    language: str
    source: str

    def attribute(self, name: str) -> str | None:
        match = re.search(ATTRIBUTE_PATTERN.format(name=re.escape(name)), self.info)
        if not match:
            return None
        return next(value for value in match.group("double", "single", "bare") if value is not None)


def fence_language(info: str) -> str:
    """Match the language forms accepted by Python-Markdown fenced_code."""

    stripped = info.strip()
    class_match = re.search(r"(?:^|[\s{])\.([\w.+#-]+)(?=\s|}|$)", stripped)
    if class_match:
        return class_match.group(1).lower()
    if stripped and not stripped.startswith("{"):
        return stripped.split()[0].lower()
    return "text"


def parse_fences(markdown_source: str) -> list[Fence]:
    return [
        Fence(match.group("info").strip(), fence_language(match.group("info")), match.group("body"))
        for match in FENCE_PATTERN.finditer(markdown_source)
    ]


def body_without_front_matter(markdown_source: str) -> str:
    match = re.match(r"\A---[^\n]*\n.*?\n---[^\n]*(?:\n){1,2}", markdown_source, re.DOTALL)
    if not match:
        raise AssertionError("Magic Vault source must start with front matter")
    return markdown_source[match.end():]


class CodeBlockFormatterTests(unittest.TestCase):
    maxDiff = None

    def assert_block(
        self,
        block: Node,
        *,
        language: str,
        source: str,
        wrap: str,
        filename: str | None = None,
        title: str | None = None,
    ) -> None:
        self.assertTrue(has_class(block, "code-block"))
        self.assertEqual(block.attributes.get("data-language"), language)
        self.assertEqual(block.attributes.get("data-wrap"), wrap)

        plain_text = language in {"text", "txt", "plaintext"}
        self.assertEqual(has_class(block, "text-block"), plain_text)
        if plain_text:
            self.assertEqual(descendants(block, class_name="code-toolbar"), [])
            self.assertEqual(descendants(block, class_name="code-language"), [])
            label_text = "Text"
        else:
            toolbar = only(descendants(block, class_name="code-toolbar"), "code toolbar")
            label = only(descendants(toolbar, class_name="code-label"), "code label")
            label_text = text_content(only(descendants(label, class_name="code-language"), "language label"))
        actions = only(descendants(block, class_name="code-actions"), "code actions")
        self.assertEqual(text_content(actions), "")
        self.assertEqual(descendants(actions), [])

        filenames = descendants(block, class_name="code-filename")
        if filename is None:
            self.assertEqual(filenames, [])
        else:
            self.assertEqual(len(filenames), 1)
            self.assertEqual(text_content(filenames[0]), filename)
        hint = only(descendants(block, class_name="code-scroll-hint"), "scroll hint")
        self.assertIn("hidden", hint.attributes)
        self.assertEqual(hint.attributes.get("aria-hidden"), "true")
        if not plain_text:
            self.assertEqual(descendants(toolbar, class_name="code-scroll-hint"), [hint] if wrap == "preserve" else [])

        self.assertEqual(descendants(block, tag="details"), [])
        self.assertEqual(descendants(block, tag="summary"), [])
        self.assertEqual(descendants(block, class_name="code-disclosure"), [])

        pre = only(descendants(block, tag="pre"), "code pre")
        self.assertIn(pre, block.children)
        self.assertNotIn("hidden", pre.attributes)
        self.assertEqual(pre.attributes.get("role"), "group")
        self.assertEqual(pre.attributes.get("tabindex"), "0")
        self.assertEqual(
            pre.attributes.get("aria-label"),
            f"{title or filename or label_text} "
            f"{'block' if plain_text or wrap == 'preserve' else 'source code'}",
        )
        code = only(descendants(pre, tag="code"), "code element")
        self.assertTrue(has_class(code, f"language-{language}"))
        self.assertEqual(trim_one_final_newline(text_content(code)), trim_one_final_newline(source))

    def test_on_config_installs_the_formatter(self):
        config = {"mdx_configs": {"codehilite": {"guess_lang": False}}}

        self.assertIs(on_config(config), config)
        self.assertIs(config["mdx_configs"]["codehilite"]["pygments_formatter"], CodeBlockFormatter)

    def test_direct_markdown_solidity_contract_keeps_language_and_source(self):
        source = "contract Vault {\n    address public owner;\n}"
        rendered = render_markdown(f"```solidity\n{source}\n```\n")
        document = Document(rendered)

        blocks = descendants(document.root, class_name="code-block")
        self.assertEqual(len(blocks), 1)
        self.assert_block(blocks[0], language="solidity", source=source, wrap="auto")
        self.assertIn("span", document.tags, "Solidity source should retain Pygments syntax markup")

    def test_repeated_and_different_blocks_do_not_share_metadata_or_source(self):
        fixtures = [
            ("solidity", "auto", "Setup.sol", "contract Setup {}"),
            ("solidity", "auto", "Vault.sol", "contract Vault {}"),
            ("text", "preserve", "notes.txt", "<literal>&text"),
            ("console", "preserve", "deploy.log", "$ cast call 0x1234 owner()"),
        ]
        rendered = render_markdown(
            "\n\n".join(
                f'``` {{ .{language} filename="{filename}" }}\n{source}\n```'
                for language, _wrap, filename, source in fixtures
            )
        )
        document = Document(rendered)
        blocks = descendants(document.root, class_name="code-block")

        self.assertEqual(len(blocks), len(fixtures))
        for block, (language, wrap, filename, source) in zip(blocks, fixtures, strict=True):
            with self.subTest(filename=filename):
                self.assert_block(
                    block,
                    language=language,
                    source=source,
                    wrap=wrap,
                    filename=filename,
                )

    def test_legacy_collapse_attribute_cannot_hide_contract_source(self):
        source = "contract Vault {\n    function unlock() external {}\n}"
        rendered = render_markdown(
            f'``` {{ .solidity filename="Vault.sol" collapse="true" }}\n{source}\n```'
        )
        document = Document(rendered)
        block = only(descendants(document.root, class_name="code-block"), "code block")

        self.assert_block(
            block,
            language="solidity",
            source=source,
            wrap="auto",
            filename="Vault.sol",
        )
        self.assertEqual(text_content(only(descendants(block, tag="code"), "code element")).count("unlock"), 1)

    def test_legacy_collapse_attribute_cannot_hide_preserved_text(self):
        source = "left  = 00 01\nright = 10 11\n        -----\nresult: 10 11"
        rendered = render_markdown(f'```{{.text collapse="true"}}\n{source}\n```')
        block = only(descendants(Document(rendered).root, class_name="code-block"), "text block")
        self.assert_block(block, language="text", source=source, wrap="preserve")

    def test_flow_layout_is_opt_in_and_only_applies_to_plain_text(self):
        source = "value = 00 01 02 03\n\nresult = 10 11 12 13"
        for language in ("text", "txt", "plaintext", "console", "solidity"):
            with self.subTest(language=language):
                rendered = render_markdown(f'```{{.{language} layout="flow"}}\n{source}\n```')
                block = only(descendants(Document(rendered).root, class_name="code-block"), "code block")
                expected = "auto" if language == "solidity" else "preserve" if language == "console" else "flow"
                self.assert_block(block, language=language, source=source, wrap=expected)
        rendered = render_markdown(f'```{{.text layout="unknown"}}\n{source}\n```')
        block = only(descendants(Document(rendered).root, class_name="code-block"), "text block")
        self.assert_block(block, language="text", source=source, wrap="preserve")

    def test_text_titles_are_escaped_and_never_enter_the_copyable_source(self):
        title = '<img src=x onerror="alert(1)">'
        source = "left  = 00 01\nright = 10 11"
        rendered = highlight(source, TextLexer(), CodeBlockFormatter("language-text", title=title))
        document = Document(rendered)
        block = only(descendants(document.root, class_name="code-block"), "text block")
        self.assert_block(block, language="text", source=source, wrap="preserve", title=title)
        self.assertNotIn(title, text_content(block))
        self.assertNotIn("img", document.tags)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    def test_unspecified_and_false_collapse_attributes_do_not_create_disclosures(self):
        rendered = render_markdown(
            "```solidity\ncontract Unspecified {}\n```\n\n"
            '``` { .solidity filename="False.sol" collapse="false" }\ncontract FalseValue {}\n```'
        )
        document = Document(rendered)
        blocks = descendants(document.root, class_name="code-block")

        self.assertEqual(len(blocks), 2)
        self.assert_block(blocks[0], language="solidity", source="contract Unspecified {}", wrap="auto")
        self.assert_block(
            blocks[1],
            language="solidity",
            source="contract FalseValue {}",
            wrap="auto",
            filename="False.sol",
        )
        self.assertEqual(descendants(document.root, tag="details", class_name="code-disclosure"), [])

    def test_filename_language_and_code_are_escaped_without_creating_markup(self):
        filename = '<img src=x onerror="alert(1)">'
        source = "</code><script>alert(1)</script><img src=x onerror=alert(1)>"
        direct_output = highlight(
            source,
            TextLexer(),
            CodeBlockFormatter("language-text", filename=filename),
        )
        direct_document = Document(direct_output)
        direct_block = only(descendants(direct_document.root, class_name="code-block"), "direct code block")
        self.assert_block(
            direct_block,
            language="text",
            source=source,
            wrap="preserve",
            filename=filename,
        )
        self.assertNotIn("img", direct_document.tags)
        self.assertNotIn("script", direct_document.tags)
        self.assertNotIn("<img", direct_output)
        self.assertNotIn("<script", direct_output)
        self.assertIn("&lt;img", direct_output)
        self.assertIn("&lt;script", direct_output)

        unsafe_language = 'language-\"><img src=x onerror=alert(1)>'
        unsafe_output = highlight(
            source,
            TextLexer(),
            CodeBlockFormatter(unsafe_language, filename=filename),
        )
        unsafe_document = Document(unsafe_output)
        unsafe_block = only(descendants(unsafe_document.root, class_name="code-block"), "unsafe language block")
        self.assert_block(
            unsafe_block,
            language="text",
            source=source,
            wrap="preserve",
            filename=filename,
        )
        self.assertNotIn("img", unsafe_document.tags)
        self.assertNotIn("script", unsafe_document.tags)
        self.assertNotIn("<img", unsafe_output)
        self.assertNotIn("<script", unsafe_output)

    def test_line_number_options_do_not_change_the_copyable_source_structure(self):
        source = "contract Vault {\n    uint256 value = 1;\n}"
        for option in (True, "table", "inline"):
            with self.subTest(linenos=option):
                rendered = highlight(
                    source,
                    TextLexer(),
                    CodeBlockFormatter("language-solidity", linenos=option),
                )
                document = Document(rendered)
                block = only(descendants(document.root, class_name="code-block"), "code block")
                self.assert_block(block, language="solidity", source=source, wrap="auto")
                self.assertEqual(len(descendants(block, tag="pre")), 1)
                self.assertEqual(descendants(block, tag="table"), [])
                self.assertEqual(descendants(block, class_name="linenos"), [])

    def test_markdown_escapes_untrusted_code_as_text(self):
        source = "</code><script>alert(1)</script><img src=x onerror=alert(1)>"
        rendered = render_markdown(f"```text\n{source}\n```")
        document = Document(rendered)
        block = only(descendants(document.root, class_name="code-block"), "code block")

        self.assert_block(block, language="text", source=source, wrap="preserve")
        self.assertNotIn("img", document.tags)
        self.assertNotIn("script", document.tags)
        self.assertNotIn("<img", rendered)
        self.assertNotIn("<script", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&lt;script", rendered)


class MagicVaultCodeBlockBuildTests(unittest.TestCase):
    """Validate the complete Magic Vault article after ``mkdocs build --strict``."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        assert MAGIC_VAULT_HTML.is_file(), "Run mkdocs build --strict before testing code blocks"
        assert MAGIC_VAULT_SOURCE.is_file(), "The built Magic Vault Markdown source is missing"
        cls.markdown = MAGIC_VAULT.read_text(encoding="utf-8")
        cls.fences = parse_fences(cls.markdown)
        cls.output = MAGIC_VAULT_HTML.read_text(encoding="utf-8")
        cls.document = Document(cls.output)
        cls.blocks = descendants(cls.document.root, class_name="code-block")

    def test_all_fences_render_in_order_with_expected_language_counts_and_source(self):
        self.assertEqual(len(self.fences), 61)
        self.assertEqual(
            Counter(fence.language for fence in self.fences),
            Counter({"solidity": 33, "console": 1, "text": 27}),
        )
        self.assertEqual(len(self.blocks), len(self.fences))

        for index, (fence, block) in enumerate(zip(self.fences, self.blocks, strict=True), start=1):
            with self.subTest(block=index, language=fence.language):
                self.assertEqual(block.attributes.get("data-language"), fence.language)
                self.assertEqual(
                    block.attributes.get("data-wrap"),
                    "auto" if fence.language == "solidity" else "flow" if fence.attribute("layout") == "flow" else "preserve",
                )
                if fence.language == "text":
                    self.assertTrue(has_class(block, "text-block"))
                    self.assertEqual(descendants(block, class_name="code-toolbar"), [])
                else:
                    toolbar = only(descendants(block, class_name="code-toolbar"), "code toolbar")
                    self.assertEqual(len(descendants(toolbar, class_name="code-label")), 1)
                actions = only(descendants(block, class_name="code-actions"), "code actions")
                self.assertEqual(text_content(actions), "")
                self.assertEqual(descendants(actions), [])
                hint = only(descendants(block, class_name="code-scroll-hint"), "scroll hint")
                if fence.language != "text":
                    self.assertEqual(descendants(toolbar, class_name="code-scroll-hint"), [hint] if fence.language == "console" else [])

                pre = only(descendants(block, tag="pre"), "code pre")
                self.assertEqual(pre.attributes.get("role"), "group")
                self.assertEqual(pre.attributes.get("tabindex"), "0")
                suffix = " source code" if fence.language == "solidity" else " block"
                self.assertTrue(pre.attributes.get("aria-label", "").endswith(suffix))
                code = only(descendants(pre, tag="code"), "code element")
                self.assertTrue(has_class(code, f"language-{fence.language}"))
                self.assertEqual(
                    trim_one_final_newline(text_content(code)),
                    fence.source.strip("\n"),  # CodeHilite normalizes blank lines at fence boundaries.
                )

    def test_source_copy_is_exact_article_body_without_front_matter(self):
        self.assertEqual(
            MAGIC_VAULT_SOURCE.read_text(encoding="utf-8"),
            body_without_front_matter(self.markdown),
        )

    def test_full_contracts_and_text_examples_have_no_disclosures(self):
        filenames = [
            text_content(filename)
            for filename in descendants(self.document.root, class_name="code-filename")
        ]
        self.assertEqual(filenames, ["Setup.sol", "Vault.sol", "Solver.sol"])

        for index, (fence, block) in enumerate(zip(self.fences, self.blocks, strict=True), start=1):
            with self.subTest(block=index, language=fence.language):
                self.assertIsNone(fence.attribute("collapse"))
                self.assertEqual(descendants(block, tag="details"), [])
                self.assertEqual(descendants(block, tag="summary"), [])
                self.assertEqual(descendants(block, class_name="code-disclosure"), [])
                pre = only(descendants(block, tag="pre"), "code pre")
                self.assertIn(pre, block.children)
                self.assertNotIn("hidden", block.attributes)
                self.assertNotIn("hidden", pre.attributes)
                if fence.attribute("title"):
                    self.assertEqual(pre.attributes.get("aria-label"), f'{fence.attribute("title")} block')

    def test_shift_examples_keep_short_byte_rows_and_separate_discarded_bytes(self):
        fixtures = {
            "Right shift": (6, "00 00 00 00 10 23 32 45", "54 67 76 89"),
            "Left shift": (5, "32 45 54 67 76 89 00 00", "10 23"),
        }
        original = "10 23 32 45 54 67 76 89"
        for title, (line_count, shifted, discarded) in fixtures.items():
            with self.subTest(title=title):
                matching = [fence for fence in self.fences if fence.attribute("title") == title]
                self.assertEqual(len(matching), 1)
                fence = matching[0]
                self.assertEqual(fence.language, "text")
                self.assertIsNone(fence.attribute("layout"), "Shift byte rows must keep their alignment")
                lines = fence.source.strip("\n").splitlines()
                self.assertEqual(len(lines), line_count)
                self.assertEqual(lines[1], original)
                self.assertEqual(lines[3], shifted)
                self.assertEqual(len(lines[1]), 23)
                self.assertEqual(len(lines[3]), 23)
                self.assertEqual(lines[-1], f"ပျောက်: {discarded}")
                self.assertTrue(all(line == line.strip() for line in lines))
                self.assertNotIn("[", fence.source)
                self.assertNotIn("→", fence.source)
                self.assertNotIn("←", fence.source)

    def test_only_independent_text_explanations_wrap(self):
        text_fences = [fence for fence in self.fences if fence.language == "text"]
        flow_indices = [index for index, fence in enumerate(text_fences) if fence.attribute("layout") == "flow"]
        self.assertEqual(flow_indices, [0, 1, 6, 8, 17, 18, 21, 23, 26])
        for fence in text_fences:
            if any(marker in fence.source for marker in ("[", "│", "─", "---")):
                self.assertIsNone(fence.attribute("layout"), "Byte columns and ASCII diagrams must preserve alignment")

    def test_solidity_syntax_classes_and_fence_attributes_do_not_leak_into_html(self):
        for css_class in ("kt", "nv", "ni"):
            with self.subTest(css_class=css_class):
                self.assertTrue(descendants(self.document.root, class_name=css_class))

        leaked_fences = [
            text_content(code)
            for code in descendants(self.document.root, tag="code")
            if re.search(
                r"^(?:solidity|console|text)\s+\{[^}]*\b(?:filename|collapse)\s*=",
                text_content(code),
                re.DOTALL,
            )
        ]
        self.assertEqual(leaked_fences, [])


if __name__ == "__main__":
    unittest.main()
