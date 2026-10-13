"""Exercise the built site at a GitHub Pages-style subpath with Playwright."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
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
