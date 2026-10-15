"""Exercise the built site at a GitHub Pages-style subpath with Playwright."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
RESULTS = ROOT / "test-results"
PREFIX = "/kokogray-lab/"


class ProjectHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        request_path = unquote(urlsplit(path).path)
        if not request_path.startswith(PREFIX):
            return str(SITE / "_outside_project_prefix_")
        return super().translate_path(request_path[len(PREFIX) - 1:])

    def log_message(self, format, *args):
        pass


def launch_browser(playwright):
    executable = os.environ.get("BROWSER_EXECUTABLE")
    if executable:
        return playwright.chromium.launch(executable_path=executable)
    try:
        return playwright.chromium.launch()
    except Exception as original:
        for channel in ("chrome", "msedge"):
            try:
                return playwright.chromium.launch(channel=channel)
            except Exception:
                continue
        raise original


def assert_no_horizontal_overflow(page):
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    ), f"Page overflows horizontally: {page.url}"


def assert_reference_styles(page, expected):
    for selector, properties in expected.items():
        actual = page.locator(selector).first.evaluate(
            "(element, keys) => { const style = getComputedStyle(element); "
            "return Object.fromEntries(keys.map(key => [key, style[key]])); }",
            list(properties),
        )
        for key, value in properties.items():
            assert actual[key] == value, f"{selector} {key}: {actual[key]!r}, expected {value!r}"


def assert_reference_box(page, selector, expected):
    actual = page.locator(selector).first.bounding_box()
    assert actual is not None, f"Missing visible reference component: {selector}"
    for key, value in expected.items():
        assert abs(actual[key] - value) <= 0.1, f"{selector} {key}: {actual[key]}, expected {value}"


def check_reference_theme(page, base, checks):
    reference = json.loads((ROOT / "tests/reference_theme.json").read_text(encoding="utf-8"))
    article = base + "2026/lab-notebook/writeup-template/"
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    page.goto(article, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.evaluate("""() => {
      const sample = document.createElement('p');
      sample.className = 'reference-type-sample';
      sample.innerHTML = '<strong>Typography sample</strong> <a href="#main-content">Link sample</a>';
      document.querySelector('.page-content').append(sample);
    }""")
    page.mouse.move(0, 0)
    assert_reference_styles(page, reference["desktop_styles"])
    for selector, dimensions in reference["desktop_boxes"].items():
        assert_reference_box(page, selector, dimensions)
    expect(page.locator(".breadcrumbs li")).to_have_text(["2026", "Lab notebook"])
    expect(page.locator(".search-shortcut kbd")).to_have_count(2)
    expect(page.locator(".nav-link .icon")).to_have_count(0)
    for theme, styles in reference["palettes"].items():
        page.locator(f".outline-footer [data-set-theme='{theme}']").click()
        page.mouse.move(0, 0)
        page.evaluate("window.scrollTo(0, 0)")
        assert_reference_styles(page, styles)
        page.screenshot(path=str(RESULTS / f"reference-desktop-{theme}.png"))
    checks.append("Measured reference desktop geometry, component typography, and both color palettes")

    for dimensions in reference["responsive"]:
        width = dimensions["viewport"]
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(article, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        assert_reference_box(page, ".page-main", {"x": dimensions["x"], "width": dimensions["width"]})
        assert_reference_styles(page, {
            ".page-title": {"fontSize": dimensions["title"]},
            ".page-content h2": {"fontSize": dimensions["section"]},
            ".page-content h3": {"fontSize": dimensions["subsection"]},
        })
        expect(page.locator("[data-set-theme]:visible")).to_have_count(3)
        assert_no_horizontal_overflow(page)
        if width == 390:
            assert_reference_box(page, ".mobile-outline > summary", {
                "x": 346.5, "y": 90, "width": 27.5, "height": 27.5,
            })
            for theme in ("light", "dark"):
                page.locator(f".mobile-page-theme [data-set-theme='{theme}']").click()
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(RESULTS / f"reference-mobile-{theme}.png"))
    checks.append("Reference article widths and container-responsive headings from 320 to 1920 pixels")


def check_top_theme_toggle(page, base, checks):
    article = base + "introduction-to-blockchain/magic-vault/"
    page.emulate_media(reduced_motion="reduce")
    for width in (320, 390, 639, 640, 768, 1023, 1024, 1280, 1440, 1920):
        page.set_viewport_size({"width": width, "height": 844})
        page.goto(article, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        toggle = page.locator(".site-header [data-toggle-theme]")
        picker = ".outline-footer" if width >= 1280 else ".mobile-page-theme"
        for theme in ("dark", "light"):
            page.locator(f"{picker} [data-set-theme='{theme}']").click()
            page.evaluate("window.scrollTo(0, 0)")
            other = "light" if theme == "dark" else "dark"
            expect(toggle).to_have_attribute("aria-label", f"Switch to {other} mode")
            expect(toggle).to_have_attribute("title", f"Switch to {other} mode")
            expect(toggle.locator(f".theme-toggle-{other}")).to_be_visible()
            expect(toggle.locator(f".theme-toggle-{theme}")).not_to_be_visible()
            box = toggle.bounding_box()
            header = page.locator(".site-header").bounding_box()
            identity = page.locator(".header-identity").bounding_box()
            actions = page.locator(".header-actions").bounding_box()
            search = page.locator(".search-trigger").bounding_box()
            assert box["width"] >= 44 and box["height"] >= 44, (width, box)
            assert 0 <= box["y"] and box["y"] + box["height"] <= header["height"], (width, box)
            assert identity["x"] + identity["width"] <= actions["x"], width
            assert box["x"] + box["width"] <= search["x"], width
            assert_no_horizontal_overflow(page)
            toggle.focus()
            toggle.press("Enter")
            expect(page.locator("html")).to_have_attribute("data-theme", other)
            expect(page.locator("html")).to_have_attribute("data-theme-preference", other)
            expect(toggle).to_have_attribute("aria-label", f"Switch to {theme} mode")
            assert page.evaluate("localStorage.getItem('kokogray-theme')") == other
            assert page.locator("[data-set-theme]").evaluate_all(
                "(buttons, selected) => buttons.every(button => button.getAttribute('aria-pressed') === String(button.dataset.setTheme === selected))",
                other,
            )
            toggle.press("Space")
            expect(page.locator("html")).to_have_attribute("data-theme", theme)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        assert 0 <= toggle.bounding_box()["y"] < 64, width
        if width in (390, 1440):
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(RESULTS / f"top-theme-{width}.png"))
    checks.append("Top light/dark toggle fits 320–1920px headers, stays reachable, and supports keyboard switching")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(article, wait_until="networkidle")
    toggle = page.locator("[data-toggle-theme]")
    page.locator(".mobile-page-theme [data-set-theme='dark']").click()
    toggle.click()
    page.reload(wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    expect(toggle).to_have_attribute("aria-label", "Switch to dark mode")
    page.goto(base, wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.locator(".mobile-page-theme [data-set-theme='system']").click()
    page.emulate_media(color_scheme="dark")
    expect(toggle).to_have_attribute("aria-label", "Switch to light mode")
    expect(toggle.locator(".theme-toggle-light")).to_be_visible()
    page.emulate_media(color_scheme="light")
    expect(toggle).to_have_attribute("aria-label", "Switch to dark mode")
    expect(toggle.locator(".theme-toggle-dark")).to_be_visible()
    toggle.click()
    expect(page.locator("html")).to_have_attribute("data-theme-preference", "dark")
    page.emulate_media(color_scheme="light")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    checks.append("Top toggle persists across pages and stays synchronized with Light/System/Dark controls")


def contrast_ratio(foreground, background):
    def luminance(color):
        channels = [int(value) / 255 for value in re.findall(r"\d+", color)[:3]]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))

    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + .05) / (low + .05)


def magic_vault_fences():
    """Return Magic Vault fence metadata in article order for byte-for-byte checks."""

    source = (ROOT / "docs/introduction-to-blockchain/magic-vault.md").read_text(encoding="utf-8")
    pattern = re.compile(
        r"^```(?P<info>[^\r\n]*)\r?\n(?P<body>.*?)(?=^```[ \t]*$)^```[ \t]*$",
        re.MULTILINE | re.DOTALL,
    )
    fences = [
        (match.group("info"), match.group("body").strip("\n"))
        for match in pattern.finditer(source)
    ]
    assert len(fences) == 61, f"Expected 61 Magic Vault fences, found {len(fences)}"
    return fences


def check_code_blocks(browser, base, origin, checks, errors, failures):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, reduced_motion="reduce",
    )
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    article = base + "introduction-to-blockchain/magic-vault/"
    fences = magic_vault_fences()
    expected_sources = [source for _, source in fences]
    expected_contracts = {
        re.search(r'filename="([^"]+)"', info).group(1): source
        for info, source in fences
        if re.search(r'filename="([^"]+)"', info)
    }
    assert set(expected_contracts) == {"Setup.sol", "Vault.sol", "Solver.sol"}

    def assert_all_pre_visible(target):
        pre = target.locator(".code-block pre")
        expect(pre).to_have_count(61)
        assert pre.evaluate_all(
            "elements => elements.every(element => element.checkVisibility({contentVisibilityAuto: true}) && "
            "element.scrollHeight <= element.clientHeight + 1)"
        ), "Every source listing must be visible and vertically unclipped without opening a disclosure"

    def assert_rendered_sources(target):
        actual = [
            text.removesuffix("\n")
            for text in target.locator(".code-block code").all_text_contents()
        ]
        assert actual == expected_sources, "Rendered listings do not match their Markdown source bytes"

    def copy_every_listing():
        for index, expected_source in enumerate(expected_sources):
            block = page.locator(".code-block").nth(index)
            block.get_by_role("button", name="Copy code", exact=True).click()
            page.wait_for_function(
                "async expected => await navigator.clipboard.readText() === expected",
                arg=expected_source,
            )

    for width in (320, 390, 768, 1440):
        for theme in ("dark", "light"):
            page.set_viewport_size({"width": width, "height": 844 if width < 640 else 1000})
            page.goto(article, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            theme_picker = ".outline-footer" if width >= 1280 else ".mobile-page-theme"
            page.locator(f"{theme_picker} [data-set-theme='{theme}']").click()
            expect(page.locator(".code-block")).to_have_count(61)
            expect(page.locator('.code-block[data-language="solidity"]')).to_have_count(33)
            expect(page.locator('.code-block[data-language="console"]')).to_have_count(1)
            expect(page.locator('.code-block[data-language="text"]')).to_have_count(27)
            expect(page.locator(".code-block details, .code-block summary, .code-disclosure")).to_have_count(0)
            assert_all_pre_visible(page)
            assert_rendered_sources(page)

            for filename, expected_source in expected_contracts.items():
                block = page.locator(".code-block").filter(has=page.locator(".code-filename", has_text=filename))
                expect(block.locator(".code-language")).to_have_text("Solidity")
                assert block.locator("code").text_content().removesuffix("\n") == expected_source
                expect(block.locator("pre")).to_be_visible()
                button = block.get_by_role("button", name="Copy code", exact=True)
                button.focus()
                button.press("Enter")
                expect(page.locator(".toast")).to_have_text("Code copied")
                page.wait_for_function("async expected => await navigator.clipboard.readText() === expected", arg=expected_source)

            if width == 390 and theme == "dark":
                copy_every_listing()

            assert_no_horizontal_overflow(page)
            layout = page.locator(".code-block").evaluate_all("""blocks => blocks.map(block => {
              const pre = block.querySelector('pre');
              const toolbar = block.querySelector('.code-toolbar');
              const copy = block.querySelector('.code-copy');
              const code = block.querySelector('code');
              return {
                language: block.dataset.language,
                mode: block.dataset.wrap,
                toolbarBottom: toolbar?.getBoundingClientRect().bottom,
                toolbarHeight: toolbar?.getBoundingClientRect().height,
                hintInToolbar: toolbar?.contains(block.querySelector('.code-scroll-hint')),
                copyBottom: copy.getBoundingClientRect().bottom,
                copyLeft: copy.getBoundingClientRect().left,
                preTop: pre.getBoundingClientRect().top,
                preRight: pre.getBoundingClientRect().right,
                overflow: pre.scrollWidth - pre.clientWidth,
                verticalOverflow: pre.scrollHeight - pre.clientHeight,
                font: getComputedStyle(code).fontSize,
                lineHeight: getComputedStyle(code).lineHeight,
                whiteSpace: getComputedStyle(code).whiteSpace,
                wrap: block.querySelector('.code-wrap')?.getAttribute('aria-pressed'),
                copyHeight: copy.getBoundingClientRect().height,
                tabIndex: pre.tabIndex,
                role: pre.getAttribute('role'),
                hintVisible: !block.querySelector('.code-scroll-hint').hidden
              };
            })""")
            for block in layout:
                assert block["copyBottom"] <= block["preTop"] + .1 or block["copyLeft"] >= block["preRight"] - .1, block
                if block["language"] == "text":
                    assert block.get("toolbarBottom") is None, block
                else:
                    assert block["toolbarBottom"] <= block["preTop"] + .1, block
                assert block["font"] == "14px" and block["lineHeight"] == "20px", block
                assert block["verticalOverflow"] <= 1, block
                assert block["role"] == "group", block
                assert block["hintVisible"] == (block["overflow"] > 1), block
                assert block["tabIndex"] == (0 if block["overflow"] > 1 else -1), block
                if block["language"] == "solidity":
                    assert block["wrap"] == ("true" if width < 640 else "false"), block
                    assert block["whiteSpace"] == ("pre-wrap" if width < 640 else "pre"), block
                    if width < 640:
                        assert block["overflow"] <= 1, block
                        assert block["copyHeight"] >= 44, block
                elif block["language"] == "text":
                    assert block["wrap"] is None, block
                    assert block["whiteSpace"] == ("pre-wrap" if block["mode"] == "flow" else "pre"), block
                    assert block["copyHeight"] >= 44, block
                    if block["mode"] == "flow":
                        assert block["overflow"] <= 1, block
                else:
                    assert block["wrap"] is None and block["whiteSpace"] == "pre", block
                    assert block["hintInToolbar"], block
                    assert block["toolbarHeight"] <= (45 if width < 640 else 36), block
                    if width < 640:
                        assert block["copyHeight"] >= 44, block

            tokens = page.locator('.code-block[data-language="solidity"] code span').evaluate_all("""elements => {
              const result = {};
              elements.forEach(element => {
                if (!element.textContent.trim()) return;
                const block = element.closest('.code-block');
                result[element.className] = {
                  color: getComputedStyle(element).color,
                  background: getComputedStyle(block).backgroundColor,
                  foreground: getComputedStyle(block).color
                };
              });
              return result;
            }""")
            for name, token in tokens.items():
                assert contrast_ratio(token["color"], token["background"]) >= 4.5, (theme, name, token)
            for name in ("kt", "nv", "ni"):
                assert tokens[name]["color"] != tokens[name]["foreground"], (theme, name)

            vault = page.locator(".code-block").filter(has=page.locator(".code-filename", has_text="Vault.sol"))
            wrap = vault.get_by_role("button", name="Wrap lines", exact=True)
            expected_initial = "true" if width < 640 else "false"
            wrap.focus()
            wrap.press("Space")
            expect(wrap).to_have_attribute("aria-pressed", "false" if width < 640 else "true")
            expect(vault.locator("code")).to_have_css("white-space", "pre" if width < 640 else "pre-wrap")
            vault.get_by_role("button", name="Copy code", exact=True).click()
            page.wait_for_function("async expected => await navigator.clipboard.readText() === expected", arg=expected_contracts["Vault.sol"])
            wrap.click()
            expect(wrap).to_have_attribute("aria-pressed", expected_initial)
            if width in (390, 1440):
                page.locator("#setupsol").evaluate("element => element.scrollIntoView()")
                page.screenshot(path=str(RESULTS / f"code-{width}-{theme}-setup.png"))
                vault.scroll_into_view_if_needed()
                page.screenshot(path=str(RESULTS / f"code-{width}-{theme}-vault.png"))

    checks.append("All 61 Magic Vault listings are visible immediately, byte-exact, and copyable in both themes")
    checks.append("Phone source wrapping, 44px controls, contained unwrapped diagrams, and no code overlays")
    checks.append("All rendered Solidity token categories meet 4.5:1 contrast in light and dark themes")
    checks.append("Text listings remain fully visible without disclosure controls or height caps")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(article, wait_until="networkidle")
    first_wrap = page.locator(".code-wrap").first
    expect(first_wrap).to_have_attribute("aria-pressed", "true")
    page.set_viewport_size({"width": 1440, "height": 1000})
    expect(first_wrap).to_have_attribute("aria-pressed", "false")
    first_wrap.click()
    page.set_viewport_size({"width": 390, "height": 844})
    expect(first_wrap).to_have_attribute("aria-pressed", "true")
    checks.append("Responsive wrap defaults track viewport changes and preserve explicit block choices")

    expect(page.locator(".code-block details, .code-block summary, .code-disclosure")).to_have_count(0)
    assert_all_pre_visible(page)
    page.emulate_media(media="print")
    expect(page.locator(".code-block pre")).to_have_count(61)
    assert page.locator(".code-block pre").evaluate_all(
        "elements => elements.every(element => element.checkVisibility({contentVisibilityAuto: true}) && "
        "element.scrollHeight <= element.clientHeight + 1)"
    ), "Printing must show every listing, fully unclipped, without opening anything"
    expect(page.locator(".code-copy:visible")).to_have_count(0)
    expect(page.locator(".code-scroll-hint:visible")).to_have_count(0)
    page.emulate_media(media="screen")
    assert_all_pre_visible(page)
    assert_rendered_sources(page)
    checks.append("Printing shows all 61 listings directly without disclosure state changes")
    context.close()

    no_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
    static_page = no_js.new_page()
    for width in (320, 390):
        static_page.set_viewport_size({"width": width, "height": 844})
        static_page.goto(article, wait_until="networkidle")
        expect(static_page.locator(".code-toolbar")).to_have_count(34)
        expect(static_page.locator(".text-block .code-toolbar")).to_have_count(0)
        expect(static_page.locator(".code-actions button")).to_have_count(0)
        expect(static_page.locator(".code-block details, .code-block summary, .code-disclosure")).to_have_count(0)
        expect(static_page.locator('.code-block pre[role="region"]')).to_have_count(0)
        expect(static_page.locator("[data-toggle-theme]")).not_to_be_visible()
        assert_all_pre_visible(static_page)
        assert_rendered_sources(static_page)
        preserved = static_page.locator('.code-block[data-wrap="preserve"]')
        expect(preserved.locator('.code-scroll-hint:visible')).to_have_count(preserved.count())
        expect(static_page.locator('.text-block[data-wrap="flow"] .code-scroll-hint:visible')).to_have_count(0)
        for label in ("Right shift block", "Left shift block"):
            pre = static_page.locator(f'pre[aria-label="{label}"]')
            expect(pre).to_be_visible()
            assert pre.evaluate("element => element.scrollWidth <= element.clientWidth + 1"), (width, label)
        assert_no_horizontal_overflow(static_page)
        assert static_page.locator('.code-block[data-language="solidity"] pre').evaluate_all(
            "elements => elements.every(el => el.scrollWidth <= el.clientWidth + 1)"
        )
    static_page.goto(article, wait_until="networkidle")
    static_page.emulate_media(media="print")
    assert_all_pre_visible(static_page)
    expect(static_page.locator(".code-scroll-hint:visible")).to_have_count(0)
    no_js.close()
    checks.append("All 61 listings remain directly readable and printable without JavaScript")


def check_mobile_text_examples(browser, base, origin, checks, errors, failures):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        device_scale_factor=3, reduced_motion="reduce",
    )
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    article = base + "introduction-to-blockchain/magic-vault/"
    fences = magic_vault_fences()
    expected_text = [
        source for info, source in fences
        if re.search(r"^text(?:\s|$)|(?:^|[\s{])\.text(?:\s|}|$)", info)
    ]
    assert len(expected_text) == 27
    measurements = []

    for width in (320, 390):
        for theme in ("dark", "light"):
            page.set_viewport_size({"width": width, "height": 844})
            page.goto(article, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.locator(f".mobile-page-theme [data-set-theme='{theme}']").click()
            text_blocks = page.locator(".text-block")
            expect(text_blocks).to_have_count(27)
            expect(page.locator(".text-block .code-toolbar")).to_have_count(0)
            expect(page.locator(".code-block details, .code-block summary, .code-disclosure")).to_have_count(0)
            expect(page.locator(".code-block pre:visible")).to_have_count(61)
            mobile_layout = text_blocks.evaluate_all(r'''blocks => blocks.map((block, index) => {
              const pre = block.querySelector('pre'), code = block.querySelector('code');
              const copy = block.querySelector('.code-copy');
              const preBox = pre.getBoundingClientRect(), copyBox = copy.getBoundingClientRect();
              return {index, ariaLabel: pre.getAttribute('aria-label'), mode: block.dataset.wrap,
                height: block.getBoundingClientRect().height,
                visible: pre.checkVisibility({contentVisibilityAuto: true}),
                overflow: pre.scrollWidth - pre.clientWidth,
                verticalOverflow: pre.scrollHeight - pre.clientHeight,
                font: getComputedStyle(code).fontSize, lineHeight: getComputedStyle(code).lineHeight,
                copyWidth: copyBox.width, copyHeight: copyBox.height,
                controlsClear: copyBox.left >= preBox.right};
            })''')
            for block in mobile_layout:
                assert block["visible"], (width, block)
                assert block["font"] == "14px" and block["lineHeight"] == "20px", (width, block)
                assert block["verticalOverflow"] <= 1, (width, block)
                assert block["copyWidth"] >= 44 and block["copyHeight"] >= 44, (width, block)
                assert block["controlsClear"], (width, block)
                if block["mode"] == "flow":
                    assert block["overflow"] <= 1, (width, block)

            for index, expected in enumerate(expected_text):
                block = text_blocks.nth(index)
                assert block.locator("code").text_content().removesuffix("\n") == expected
                block.get_by_role("button", name="Copy code", exact=True).tap()
                page.wait_for_function(
                    "async expected => await navigator.clipboard.readText() === expected", arg=expected
                )

            for aria_label, maximum_height, shifted, discarded, line_count in (
                ("Right shift block", 145, "00 00 00 00 10 23 32 45", "54 67 76 89", 6),
                ("Left shift block", 125, "32 45 54 67 76 89 00 00", "10 23", 5),
            ):
                pre = page.locator(f'pre[aria-label="{aria_label}"]')
                expect(pre).to_have_count(1)
                expect(pre).to_be_visible()
                expect(pre.locator("code")).to_have_css("white-space", "pre")
                assert pre.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
                block = next(item for item in mobile_layout if item["ariaLabel"] == aria_label)
                assert block["height"] <= maximum_height, (width, aria_label, block)
                lines = pre.locator("code").text_content().strip("\n").splitlines()
                assert len(lines) == line_count, (aria_label, lines)
                assert lines[1] == "10 23 32 45 54 67 76 89", (aria_label, lines)
                assert lines[3] == shifted, (aria_label, lines)
                assert lines[-1].endswith(": " + discarded), (aria_label, lines)

            measurements.append({"width": width, "theme": theme, "blocks": mobile_layout})
            assert_no_horizontal_overflow(page)
            right_shift = page.locator('pre[aria-label="Right shift block"]')
            right_shift.scroll_into_view_if_needed()
            page.screenshot(path=str(RESULTS / f"text-examples-{width}-{theme}.png"))
            assert_no_horizontal_overflow(page)
    (RESULTS / "text-size-report.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")
    context.close()
    checks.append("All mobile text listings are fully visible, copy exactly, and retain 14px/20px source typography")
    checks.append("Right and Left shift listings fit 320px and 390px phones without internal or page overflow")


def main():
    assert (SITE / "index.html").exists(), "Run mkdocs build --strict first"
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(ProjectHandler, directory=str(SITE)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    base = origin + PREFIX
    errors = []
    failures = []
    checks = []

    try:
        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: failures.append(f"{response.status} {response.url}") if response.status >= 400 else None)

            page.goto(base, wait_until="networkidle")
            expect(page.locator(".page-title")).to_have_text("Welcome")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            expect(page.locator(".nav-link[aria-current='page']")).to_have_text("Welcome")
            assert page.evaluate("document.fonts.check('16px Inter')")
            assert_no_horizontal_overflow(page)
            page.screenshot(path=str(RESULTS / "desktop-dark.png"), full_page=True)
            checks.append("Desktop page, dark default, active navigation, local font, and no overflow")

            page.get_by_role("button", name="Light theme", exact=True).click()
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            page.reload(wait_until="networkidle")
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            page.screenshot(path=str(RESULTS / "desktop-light.png"), full_page=True)
            page.get_by_role("button", name="System theme", exact=True).click()
            page.emulate_media(color_scheme="dark")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.emulate_media(color_scheme="light")
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            page.get_by_role("button", name="Dark theme", exact=True).click()
            checks.append("Light/dark persistence and live system-theme changes")

            page.keyboard.press("Control+k")
            expect(page.locator("#search-dialog")).to_be_visible()
            page.locator("#site-search").fill("short-lived")
            expect(page.locator(".search-result").first).to_be_visible()
            page.keyboard.press("ArrowDown")
            expect(page.locator(".search-result.is-selected")).to_be_focused()
            selected_url = page.locator(".search-result.is-selected").get_attribute("href")
            page.keyboard.press("Enter")
            page.wait_for_url(selected_url, wait_until="networkidle")
            assert "knowledge-base/" in page.url, page.url
            expect(page.locator(".page-title")).to_be_visible()
            checks.append("Search index, keyboard shortcut, arrow selection, and nested navigation")

            page.keyboard.press("Control+k")
            page.locator("#site-search").fill("no-result-1234567890")
            expect(page.locator("[data-search-status]")).to_contain_text("No results")
            page.keyboard.press("Escape")
            expect(page.locator("#search-dialog")).not_to_be_visible()
            checks.append("Empty-search feedback and Escape dismissal")

            page.goto(base + "2026/lab-notebook/writeup-template/", wait_until="networkidle")
            expect(page.locator(".page-title")).to_have_text("Writeup template")
            expect(page.locator(".nav-link[aria-current='page']")).to_have_text("Writeup template")
            page.get_by_role("button", name="Copy page", exact=True).click()
            expect(page.locator(".toast")).to_have_text("Page copied as Markdown")
            clipboard = page.evaluate("navigator.clipboard.readText()")
            assert "# Writeup template" in clipboard and "## Verification" in clipboard
            page.locator(".codehilite").first.hover()
            page.get_by_role("button", name="Copy code", exact=True).first.click()
            expect(page.locator(".toast")).to_have_text("Code copied")
            assert "Participant" in page.evaluate("navigator.clipboard.readText()")
            page.get_by_role("button", name="Copy link", exact=True).click()
            expect(page.locator(".toast")).to_have_text("Link copied")
            assert page.evaluate("navigator.clipboard.readText()") == page.url
            checks.append("Direct nested-page load and page/code/link clipboard controls")

            page.locator(".page-outline a[href='#defensive-lessons']").click()
            expect(page.locator(".page-outline a[href='#defensive-lessons']")).to_have_attribute("aria-current", "location")
            page.screenshot(path=str(RESULTS / "article-dark.png"), full_page=True)
            checks.append("Deep heading anchor and scroll-aware page outline")

            for width in (320, 390, 768, 1024, 1280, 1920):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(base + "2026/lab-notebook/getting-started/", wait_until="networkidle")
                assert_no_horizontal_overflow(page)
            checks.append("No horizontal overflow at 320, 390, 768, 1024, 1280, and 1920 pixels")

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(base, wait_until="networkidle")
            menu = page.get_by_role("button", name="Open navigation", exact=True)
            menu.click()
            expect(page.locator(".site-sidebar")).to_have_attribute("aria-modal", "true")
            assert page.locator(".site-header").evaluate("element => element.inert")
            expect(page.locator(".site-sidebar [data-close-nav]")).to_be_focused()
            page.screenshot(path=str(RESULTS / "mobile-navigation.png"), full_page=True)
            page.keyboard.press("Shift+Tab")
            expect(page.locator(".drawer-theme").get_by_role("button", name="Dark theme", exact=True)).to_be_focused()
            page.keyboard.press("Tab")
            expect(page.locator(".site-sidebar [data-close-nav]")).to_be_focused()
            page.keyboard.press("Escape")
            expect(menu).to_be_focused()
            expect(menu).to_have_attribute("aria-expanded", "false")
            checks.append("Mobile drawer, focus trap, Escape, and focus restoration")

            menu.click()
            page.keyboard.press("Control+k")
            expect(page.locator("#search-dialog")).to_be_visible()
            expect(menu).to_have_attribute("aria-expanded", "false")
            page.keyboard.press("Escape")
            expect(menu).to_be_focused()
            checks.append("Search opened from the mobile drawer restores focus to the visible menu")

            menu.click()
            page.locator(".nav-depth-1 > summary").click()
            page.locator(".nav-link", has_text="Writeup template").click()
            page.wait_for_load_state("networkidle")
            expect(page.locator(".page-title")).to_have_text("Writeup template")
            assert not page.locator("body").evaluate("element => element.classList.contains('nav-open')")
            page.locator(".mobile-outline > summary").click()
            page.locator(".mobile-outline a[href='#initial-analysis']").click()
            expect(page.locator(".mobile-outline")).not_to_have_attribute("open", "")
            assert page.url.endswith("#initial-analysis")
            page.screenshot(path=str(RESULTS / "mobile-article.png"), full_page=True)
            checks.append("Mobile nested navigation and inline page outline")

            outline = page.locator(".mobile-outline")
            outline.locator("summary").click()
            page.keyboard.press("Tab")
            page.keyboard.press("Escape")
            expect(outline).not_to_have_attribute("open", "")
            expect(outline.locator("summary")).to_be_focused()
            outline.locator("summary").click()
            page.mouse.click(2, 80)
            expect(outline).not_to_have_attribute("open", "")
            checks.append("Compact mobile outline keyboard and outside-click dismissal")

            check_reference_theme(page, base, checks)
            check_top_theme_toggle(page, base, checks)
            check_code_blocks(browser, base, origin, checks, errors, failures)
            check_mobile_text_examples(browser, base, origin, checks, errors, failures)

            page.goto(base + "404.html", wait_until="networkidle")
            expect(page.locator(".page-title")).to_have_text("Page not found")
            page.get_by_role("button", name="Search documentation", exact=True).click()
            page.locator("#site-search").fill("Cloud security")
            expect(page.locator(".search-result").first).to_be_visible()
            page.keyboard.press("Escape")
            checks.append("404 shell and search under the project prefix")

            assert not errors, "Browser JavaScript errors: " + repr(errors)
            assert not failures, "Failed asset requests: " + repr(failures)
            context.close()

            no_js = browser.new_context(java_script_enabled=False, viewport={"width": 1440, "height": 900})
            static_page = no_js.new_page()
            static_page.goto(base + "2026/lab-notebook/writeup-template/")
            expect(static_page.locator(".page-title")).to_have_text("Writeup template")
            expect(static_page.locator(".page-content")).to_contain_text("Defensive lessons")
            checks.append("Documentation remains readable without JavaScript")
            static_page.set_viewport_size({"width": 390, "height": 844})
            static_page.goto(base + "2026/lab-notebook/writeup-template/")
            expect(static_page.locator(".site-sidebar .nav-link", has_text="Cloud security")).to_be_visible()
            expect(static_page.locator("[data-open-nav]")).not_to_be_visible()
            static_page.locator(".site-sidebar .nav-link", has_text="Cloud security").click()
            expect(static_page.locator(".page-title")).to_have_text("Cloud security")
            assert_no_horizontal_overflow(static_page)
            checks.append("Mobile navigation remains usable when JavaScript is disabled")
            no_js.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    report = {"checks": checks, "javascript_errors": errors, "failed_requests": failures}
    (RESULTS / "browser-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for check in checks:
        print("PASS:", check)
    print(f"Passed {len(checks)} browser checks. Screenshots: {RESULTS}")


if __name__ == "__main__":
    main()
