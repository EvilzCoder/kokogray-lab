# Kokogray Lab

A Markdown-powered security notebook with a custom, GitBook-style frontend. Closely matches the [provided reference](https://kabinet.gitbook.io/ctf-writeup/2026/wiz-cloud-security-challenge/happy-birthday): dark clean theme, Inter typography, IBM Plex Mono code, blue-tinted filled sidebar, pill navigation, and a three-column reading layout.

**Site:** https://evilzcoder.github.io/kokogray-lab/

This is an independent static website, not the hosted GitBook product. It uses the Kokogray Lab identity and original starter documentation, not the reference author's logo or articles.

## Features

- Locally hosted fonts and assets; no frontend CDN or Node.js requirement.
- Dark by default, with persistent light / dark / system theme controls.
- Nested sidebar, breadcrumbs, scroll-aware outline, and previous/next pages.
- Full-content local search with Ctrl/⌘ K, arrow-key navigation, and Enter to open.
- Mobile navigation with focus management, keyboard dismissal, and a page outline.
- Syntax-highlighted code, copy controls, Markdown page copy, tables, and callouts.
- Static nested URLs that work under the GitHub Pages project prefix.
- Strict builds, internal-link checks, browser tests, and Pages deployment via Actions.

## Local development

Requires **Python 3.11+** (CI uses Python 3.12).

```sh
python -m venv .venv
```

**Windows PowerShell**

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m mkdocs serve
```

**macOS / Linux**

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m mkdocs serve
```

Open the local URL printed by MkDocs. It reloads when Markdown or the theme changes.

## Write a page

1. Add a file such as `docs/2026/my-event/my-challenge.md`.
2. Include YAML front matter and a heading:

   ```markdown
   ---
   title: My challenge
   description: A short introduction to the problem and lesson.
   ---

   # My challenge

   ## Challenge description

   ## Analysis

   ## Verification

   ## Defensive lessons
   ```

3. Add it to `nav` in `mkdocs.yml`. Navigation order also determines previous/next links.
4. Link to pages with relative `.md` paths; MkDocs converts them to deployment-safe URLs.
5. Store images under `docs/assets/` and use relative paths.
6. Run the checks before pushing.

The starter notebook includes a [writeup template](docs/2026/lab-notebook/writeup-template.md). Starter pages are labeled as guides/templates and do not claim completed challenges.

## Test

Use the virtual environment's Python, or activate it before running:

```sh
python -m pip install -r requirements-dev.txt
python -m mkdocs build --strict
python -m unittest discover -s tests -v
python -m playwright install chromium
python scripts/browser_checks.py
```

The browser script can also use an installed Chrome or Edge. It serves the built site under `/kokogray-lab/`, checks desktop/mobile behavior, and saves screenshots to ignored `test-results/`. It also checks measured reference colors, component styles, and article geometry at seven widths against `tests/reference_theme.json`; unit tests lock the matching font binaries by SHA-256. The dark/light desktop and mobile screenshots support visual review rather than claiming pixel equivalence between different articles.

## Deploy to GitHub Pages

1. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
2. Push to `main`, or manually run **Build and deploy documentation** in Actions.
3. The workflow builds, validates, tests, uploads, and deploys `site/`.
4. Verify the workflow succeeds before treating the configured URL as live.

For a different repository or custom domain, update `site_url`, `repo_url`, and `extra.github_url` in `mkdocs.yml`. Do not commit build output or credentials.

## Project structure

```text
docs/                  Markdown pages
mkdocs.yml             Site settings and navigation
theme/                 Jinja templates and local CSS/JS/fonts
scripts/hooks.py       Markdown copy and content presentation hooks
scripts/browser_checks.py  Desktop/mobile smoke tests
tests/                 Generated-site validation
.github/workflows/     Build, tests, and Pages deployment
```

## Theme notes

The theme reproduces observed styling rather than embedding GitBook's proprietary runtime. Its colors, typography, default dark appearance, and layout were derived from the public reference. GitBook-hosted services such as AI chat and account management are not included. Search, copy, navigation, and theme switching run entirely in the static frontend.

Fonts retain their SIL Open Font License notices under `theme/assets/fonts/`. The theme uses an original Kokogray monogram. Inline controls use locally bundled Font Awesome Free 7.0.0 SVG icons under CC BY 4.0, with attribution retained in the rendered SVGs and `theme/assets/font-awesome-LICENSE.txt`. These open-source replacements are not claimed to be the reference's exact icon paths.
