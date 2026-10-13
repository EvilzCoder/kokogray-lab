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
            expect(page.get_by_role("button", name="System theme", exact=True)).to_be_focused()
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
