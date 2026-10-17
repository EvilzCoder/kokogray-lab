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
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer
from scripts.hooks import CodeBlockFormatter, on_config


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
FENCE_PATTERN = re.compile(
    r"^```(?P<info>[^\r\n]*)\r?\n(?P<body>.*?)(?=^```[ \t]*$)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
ATTRIBUTE_PATTERN = r"(?:^|\s){name}\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s}}]+))"
TEXT_LANGUAGES = {"text", "txt", "plaintext"}
FLOW_OUTPUT_LANGUAGES = TEXT_LANGUAGES | {"console", "shell-session", "pycon"}


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

        plain_text = language in TEXT_LANGUAGES
        flow_output = language in FLOW_OUTPUT_LANGUAGES and wrap == "flow"
        compact_output = plain_text or flow_output
        self.assertEqual(has_class(block, "text-block"), compact_output)

        toolbars = descendants(block, class_name="code-toolbar")
        captions = descendants(block, class_name="text-caption")
        if compact_output:
            self.assertEqual(toolbars, [])
            if filename is not None:
                only(captions, "compact output filename caption")
            else:
                self.assertEqual(captions, [])
            label_text = "Text" if plain_text else get_lexer_by_name(language).name
            if language in {"console", "shell-session"}:
                label_text = "Terminal"
        else:
            self.assertEqual(captions, [])
            toolbar = only(toolbars, "code toolbar")
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
        if not compact_output:
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
            f"{'block' if compact_output or wrap == 'preserve' else 'source code'}",
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

    def test_flow_layout_is_opt_in_for_text_and_terminal_output_only(self):
        source = "value = 00 01 02 03\n\nresult = 10 11 12 13"
        for language in ("text", "txt", "plaintext", "console", "shell-session", "pycon"):
            with self.subTest(language=language):
                rendered = render_markdown(f'```{{.{language} layout="flow"}}\n{source}\n```')
                block = only(descendants(Document(rendered).root, class_name="code-block"), "code block")
                self.assert_block(block, language=language, source=source, wrap="flow")
                self.assertTrue(has_class(block, "text-block"))
                self.assertEqual(descendants(block, class_name="code-toolbar"), [])

        for language in ("solidity", "python"):
            with self.subTest(source_language=language):
                rendered = render_markdown(f'```{{.{language} layout="flow"}}\n{source}\n```')
                block = only(descendants(Document(rendered).root, class_name="code-block"), "source block")
                self.assert_block(block, language=language, source=source, wrap="auto")
                self.assertFalse(has_class(block, "text-block"))

        rendered = render_markdown(f'```{{.text layout="unknown"}}\n{source}\n```')
        block = only(descendants(Document(rendered).root, class_name="code-block"), "text block")
        self.assert_block(block, language="text", source=source, wrap="preserve")

    def test_long_hex_wrapping_is_scoped_and_keeps_escaped_source_exact(self):
        value = "0x11223344556677889900aabbccddeeff"
        source = f'<img src="{value}" onerror="alert(1)"> & 0xabcd\nresult: {value}'
        for language, layout, wrap, count in (
            ("text", "flow", "flow", 2),
            ("txt", "flow", "flow", 2),
            ("plaintext", "flow", "flow", 2),
            ("text", None, "preserve", 0),
            ("console", "flow", "flow", 0),
            ("solidity", "flow", "auto", 0),
        ):
            with self.subTest(language=language, layout=layout):
                info = f'.{language}' + (' layout="flow"' if layout else '')
                rendered = render_markdown(f"```{{{info}}}\n{source}\n```")
                document = Document(rendered)
                block = only(descendants(document.root, class_name="code-block"), "code block")
                self.assert_block(block, language=language, source=source, wrap=wrap)
                spans = descendants(block, class_name="text-value")
                self.assertEqual([text_content(span) for span in spans], [value] * count)
                self.assertNotIn("img", document.tags)
                self.assertNotIn("script", document.tags)
                self.assertNotIn("<img", rendered)
                self.assertNotIn("0xabcd", [text_content(span) for span in spans])

    def test_default_terminal_blocks_preserve_lines_and_keep_toolbar(self):
        source = "$ cast call 0x1234 owner()\n0x1122334455667788"
        for language in ("console", "shell-session", "pycon"):
            with self.subTest(language=language):
                rendered = render_markdown(f"```{language}\n{source}\n```")
                block = only(descendants(Document(rendered).root, class_name="code-block"), "terminal block")
                self.assert_block(block, language=language, source=source, wrap="preserve")
                self.assertFalse(has_class(block, "text-block"))
                self.assertEqual(len(descendants(block, class_name="code-toolbar")), 1)

    def test_flow_terminal_caption_escapes_filename_and_title_without_copying_metadata(self):
        filename = '<terminal>&.log'
        title = '<strong>query</strong>'
        source = '$ cast call target nonce()\n7'
        rendered = highlight(
            source,
            TextLexer(),
            CodeBlockFormatter(
                "language-console",
                layout="flow",
                filename=filename,
                title=title,
            ),
        )
        document = Document(rendered)
        block = only(descendants(document.root, class_name="code-block"), "flow terminal block")
        self.assert_block(
            block,
            language="console",
            source=source,
            wrap="flow",
            filename=filename,
            title=title,
        )
        self.assertEqual(
            text_content(only(descendants(block, class_name="text-caption"), "terminal filename caption")),
            filename,
        )
        self.assertEqual(descendants(block, class_name="code-language"), [])
        self.assertEqual(descendants(block, class_name="code-toolbar"), [])
        self.assertNotIn("terminal", document.tags)
        self.assertNotIn("strong", document.tags)
        self.assertNotIn("<terminal", rendered)
        self.assertNotIn("<strong", rendered)
        self.assertIn("&lt;terminal", rendered)
        self.assertIn("&lt;strong", rendered)
        self.assertNotIn(title, text_content(block))

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
                flow_output = (
                    fence.language in FLOW_OUTPUT_LANGUAGES
                    and fence.attribute("layout") == "flow"
                )
                compact_output = fence.language in TEXT_LANGUAGES or flow_output
                expected_wrap = "flow" if flow_output else "preserve" if fence.language in FLOW_OUTPUT_LANGUAGES else "auto"

                self.assertEqual(block.attributes.get("data-language"), fence.language)
                self.assertEqual(block.attributes.get("data-wrap"), expected_wrap)
                self.assertEqual(has_class(block, "text-block"), compact_output)
                toolbars = descendants(block, class_name="code-toolbar")
                if compact_output:
                    self.assertEqual(toolbars, [])
                else:
                    toolbar = only(toolbars, "code toolbar")
                    self.assertEqual(len(descendants(toolbar, class_name="code-label")), 1)

                if compact_output:
                    if fence.attribute("filename"):
                        only(descendants(block, class_name="text-caption"), "compact output filename caption")
                    else:
                        self.assertEqual(descendants(block, class_name="text-caption"), [])
                else:
                    self.assertEqual(descendants(block, class_name="text-caption"), [])

                actions = only(descendants(block, class_name="code-actions"), "code actions")
                self.assertEqual(text_content(actions), "")
                self.assertEqual(descendants(actions), [])
                hint = only(descendants(block, class_name="code-scroll-hint"), "scroll hint")
                if not compact_output:
                    self.assertEqual(descendants(toolbar, class_name="code-scroll-hint"), [hint] if expected_wrap == "preserve" else [])

                pre = only(descendants(block, tag="pre"), "code pre")
                self.assertEqual(pre.attributes.get("role"), "group")
                self.assertEqual(pre.attributes.get("tabindex"), "0")
                suffix = " block" if compact_output or expected_wrap == "preserve" else " source code"
                self.assertTrue(pre.attributes.get("aria-label", "").endswith(suffix))
                code = only(descendants(pre, tag="code"), "code element")
                self.assertTrue(has_class(code, f"language-{fence.language}"))
                self.assertEqual(
                    trim_one_final_newline(text_content(code)),
                    fence.source.strip("\n"),  # CodeHilite normalizes blank lines at fence boundaries.
                )

        self.assertEqual(len(descendants(self.document.root, class_name="text-block")), 28)
        self.assertEqual(len(descendants(self.document.root, class_name="code-toolbar")), 33)

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

    def one_text_fence(self, title: str) -> Fence:
        return only(
            [fence for fence in self.fences if fence.attribute("title") == title],
            f"{title} text fence",
        )

    def test_aligned_diagrams_preserve_lines_instead_of_using_flow(self):
        preserved = {
            "Bytes32 to bytes16", "Mixed value", "Bytes16 to bytes8",
            "Right shift", "Left shift", "Bitwise OR", "Architecture",
            "64-bit shift", "Password halves", "Input byte layout",
            "Password layout", "Password bitwise OR", "Helper call flow",
            "Password assembly", "Contract call flow",
        }
        text_fences = [fence for fence in self.fences if fence.language == "text"]
        self.assertEqual(
            {fence.attribute("title") for fence in text_fences if fence.attribute("layout") != "flow"},
            preserved,
        )
        for fence in text_fences:
            with self.subTest(title=fence.attribute("title")):
                if fence.attribute("title") in preserved:
                    self.assertIsNone(fence.attribute("layout"), "Diagram rows must not wrap out of alignment")
                else:
                    self.assertEqual(fence.attribute("layout"), "flow")

    def test_architecture_retains_both_boxes_branches_and_target_connector(self):
        source = self.one_text_fence("Architecture").source
        for border in (
            "┌" + "─" * 45 + "┐", "└" + "─" * 45 + "┘",
            "┌" + "─" * 54 + "┐", "└" + "─" * 54 + "┘",
        ):
            self.assertIn(border, source)
        self.assertIn("│  TARGET " + "─" * 36 + "┼─────┐", source)
        self.assertIn("│  ├── msg.value == 1 ether", source)
        self.assertIn("│  └── new Vault()", source)
        self.assertIn("│  └── Vault ရဲ့ holder", source)
        for field, branch in (
            ("map.holder", "├"), ("owner", "├"), ("passphrase", "├"),
            ("nonce", "├"), ("isUnlocked", "└"),
        ):
            self.assertIn(f"│  {branch}── {field}", source)
        for function, branch in (
            ("mapHolder()", "├"), ("unlock(bytes16 password)", "├"),
            ("claimContent()", "└"), ("_magicPassword()", "├"),
            ("_generateKey(reductor)", "└"),
        ):
            self.assertIn(f"│  {branch}── {function}", source)
        lines = source.strip("\n").splitlines()
        self.assertEqual(lines[1:4], ["                       │", "                       │ 1 ETH နဲ့ deploy", "                       ▼"])
        self.assertEqual(source.count("▼"), 2)
        target = next(index for index, line in enumerate(lines) if "TARGET" in line)
        arrow = lines.index("                                                   ▼")
        self.assertTrue(all(line.endswith("     │") for line in lines[target + 1:arrow]))
        self.assertTrue(lines[arrow + 1].startswith("┌"), "TARGET must connect down to the Vault box")

    def test_call_flows_retain_connectors_order_and_both_sender_rows(self):
        helper = self.one_text_fence("Helper call flow").source.strip("\n").splitlines()
        self.assertEqual(len(helper), 16)
        for index in (1, 4, 7, 10, 13):
            self.assertEqual(helper[index:index + 2], ["                  │", "                  ▼"])
        for line, value in zip(helper[::3], ("Wallet", "Vault ရဲ့ owner", "_key1", "owner အပိုင်း", "Vault.unlock(password)", "Vault.claimContent()"), strict=True):
            self.assertIn(value, line)

        callers = self.one_text_fence("Contract call flow").source
        self.assertIn("Wallet\n  │\n  └── Solver.solve(Vault address)", callers)
        self.assertIn("        ├── Vault.unlock(password)", callers)
        self.assertIn("        └── Vault.claimContent()", callers)
        self.assertLess(callers.index("Vault.unlock(password)"), callers.index("Vault.claimContent()"))
        self.assertIn("│   Solver ထဲက msg.sender = Wallet address", callers)
        self.assertEqual(callers.count("Vault ထဲက msg.sender = Solver address"), 2)
        self.assertIn("              map.holder = Solver address", callers)
        self.assertEqual(callers.strip("\n").splitlines()[4], "        │")
        self.assertEqual(callers.strip("\n").splitlines()[7], "        │")

    def test_calculation_separators_stay_aligned_with_operands_and_results(self):
        for title, column, width in (
            ("Mixed value", 12, 34), ("Password bitwise OR", 8, 34),
            ("Password assembly", 13, 33),
        ):
            with self.subTest(title=title):
                lines = self.one_text_fence(title).source.strip("\n").splitlines()
                self.assertEqual(len(lines), 4)
                self.assertEqual(lines[2], " " * column + "-" * width)
                for index in (0, 1, 3):
                    self.assertEqual(len(lines[index][column:]), width)
                    self.assertRegex(lines[index][column:], r"^(?:0x[0-9a-f]+|[0-9A-F]+ [0-9A-F]+)$")

        source = self.one_text_fence("Bitwise OR").source
        self.assertIn("right = 00 00 00 00 10 23 32 45\nleft  = 32 45 54 67 76 89 00 00\n        -----------------------\nOR    = 32 45 54 67 76 AB 32 45", source)
        self.assertIn("0x10 = 0001 0000\n0x76 = 0111 0110\n       ---------\nOR   = 0111 0110 = 0x76", source)
        self.assertIn("0x23 = 0010 0011\n0x89 = 1000 1001\n       ---------\nOR   = 1010 1011 = 0xAB", source)
        self.assertTrue(source.rstrip().endswith("0x3245546776ab3245"))

    def test_byte_brackets_and_password_halves_keep_their_grouping(self):
        fixtures = {
            "Bytes32 to bytes16": (
                "[11][22][33][44][55][66][77][88]", "[99][00][aa][bb][cc][dd][ee][ff]",
                "[ff][ee][dd][cc][bb][aa][00][99]", "[88][77][66][55][44][33][22][11]",
            ),
            "Bytes16 to bytes8": (
                "[10][23][32][45][54][67][76][89] --- < ယူမဲ့ အပိုင်း >",
                "[99][00][aa][bb][cc][dd][ee][ff] --- < ဖြတ်ချမဲ့ အပိုင်း >",
            ),
            "64-bit shift": (
                "[32][45][54][67][76][ab][32][45][00][00][00][00][00][00][00][00]",
                "[00][00][00][00][00][00][00][00][32][45][54][67][76][ab][32][45]",
            ),
            "Input byte layout": (
                "[11][22][33][44]           [32][45][54][67]",
                "[55][66][77][88]           [76][ab][32][45]",
                "   ဖြတ်ချမယ်                  ယူမယ်",
                "uint64(_input) : 0x3245546776ab3245", "_secretKey    : 0x3245546776ab3245",
            ),
            "Password halves": (
                "[ အရှေ့ပိုင်း 8 bytes ][ အနောက်ပိုင်း 8 bytes ]",
                "        upper                  lower", "        64-bit                 64-bit",
            ),
            "Password layout": ("[ owner ရဲ့ နောက်ဆုံး 8 bytes ][ _secretKey 8 bytes ]",),
        }
        for title, expected_lines in fixtures.items():
            with self.subTest(title=title):
                lines = self.one_text_fence(title).source.splitlines()
                for line in expected_lines:
                    self.assertIn(line, lines)
        source = self.one_text_fence("Bytes32 to bytes16").source
        self.assertIn("0x11223344556677889900aabbccddeeffffeeddccbbaa00998877665544332211", source)
        self.assertLess(source.index("အရှေ့ဆုံး 16 bytes"), source.index("အနောက်ဆုံး 16 bytes"))

    def test_terminal_prompts_and_separate_state_calculations_are_restored(self):
        terminal = only([fence for fence in self.fences if fence.language == "console"], "terminal transcript")
        self.assertEqual(terminal.attribute("layout"), "flow")
        self.assertIn('export ETH_RPC_URL="http://154.57.164.69:37795/rpc"', terminal.source)
        self.assertEqual(terminal.source.count("┌──(kali㉿kali)-[~]"), 2)
        self.assertIn("└─$ cast block latest -f number\n338", terminal.source)
        self.assertIn("└─$ cast block latest -f timestamp\n1791971800", terminal.source)

        constructor = self.one_text_fence("Constructor values").source.splitlines()
        for line in ("msg.sender    = Setup Contract address", "address(this) = Vault Contract address", "owner         = Setup Contract address", "map.holder    = Vault Contract address"):
            self.assertIn(line, constructor)
        nonce = self.one_text_fence("Nonce calculation").source.splitlines()
        for line in ("    key1 အတွက် nonce = n", "    key2 အတွက် nonce = n + 1", "    Vault ရဲ့ nonce  = n ပဲ ရှိသေးတယ်", "    _key1 အတွက် nonce = n", "    _key2 အတွက် nonce = n + 1", "    နှစ်ခါတွက်ပြီး nonce = n + 2"):
            self.assertIn(line, nonce)

    def test_flow_text_value_spans_preserve_exact_long_hex_values(self):
        expected_hex_values = {
            "0x3245546776ab32450000000000000000",
            "0xaabbccddeeff0011223344551122334455667788",
        }
        spans = descendants(self.document.root, tag="span", class_name="text-value")
        values = {text_content(span) for span in spans}
        self.assertTrue(expected_hex_values <= values)

        for value in expected_hex_values:
            with self.subTest(value=value):
                span = only([candidate for candidate in spans if text_content(candidate) == value], "long hex span")
                block = next(
                    block
                    for block in self.blocks
                    if span in descendants(block, tag="span", class_name="text-value")
                )
                self.assertEqual(block.attributes.get("data-wrap"), "flow")
                self.assertEqual(descendants(span, tag="span"), [])
                self.assertEqual(text_content(span), value)
                self.assertNotIn(chr(0x200B), text_content(span))
                self.assertNotIn(chr(0xAD), text_content(span))
                self.assertNotIn("&", text_content(span))

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
