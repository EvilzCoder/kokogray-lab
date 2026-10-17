# Kokogray Lab

A Markdown-powered security notebook with a custom, GitBook-style frontend. Closely matches the [provided reference](https://kabinet.gitbook.io/ctf-writeup/2026/wiz-cloud-security-challenge/happy-birthday): dark clean theme, Inter typography, IBM Plex Mono code, blue-tinted filled sidebar, pill navigation, and a three-column reading layout.

**Site:** https://evilzcoder.github.io/kokogray-lab/

This is an independent static website, not the hosted GitBook product. It uses the Kokogray Lab identity and original starter documentation, not the reference author's logo or articles.

## Features

- Locally hosted fonts and assets; no frontend CDN or Node.js requirement.
- Dark by default, with a light/dark toggle in the top bar and persistent light / dark / system theme controls.
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

### Code blocks

Always label fences: `solidity`, `python`, or the relevant language for source; `sh` for shell commands; `console` for terminal transcripts; and `text` for diagrams, byte layouts, and explanatory output. Language guessing stays disabled so plain output is not accidentally highlighted.

Use fence attributes for filenames:

````markdown
```{.solidity filename="Vault.sol"}
contract Vault {
    // Complete source goes here.
}
```
````

Every code and text block is fully visible by default, including full contract listings. There are no collapse, expand, or Show/Hide controls. Keep the full source in the fence for reading, copying, and printing. Format long expressions across lines and dedent standalone snippets without changing their behavior.

Source code wraps by default on phones; the toolbar's **Wrap** toggle can preserve source lines or enable wrapping on desktop. Wrapping is visual only and never changes copied text. Source blocks and default terminal transcripts keep their toolbars; plain `text` examples use a compact layout with a separate 44px Copy target instead of a full language toolbar. Controls never cover the source. Line-number options are intentionally disabled so every copyable block keeps a single clean source container.

Plain text preserves columns by default for ASCII diagrams and byte layouts. Use `{.text layout="flow"}` for independent equations, prose, or results that can safely wrap to the full reading width; its Copy target floats at the side and reserves space only alongside the first two rows. Do not use it for aligned arrows or byte columns. Terminal transcripts (`console`, `shell-session`, or `pycon`) also accept `layout="flow"` when the output can wrap safely; they use the same compact full-width layout and omit the full toolbar. Long hex values in flowing plain text can break within the value without inserting characters into the copied text. Flow is ignored for source languages such as Solidity. An optional title gives a text block an accessible label without adding a toolbar or hiding its content:

````markdown
```{.text title="Byte layout"}
10 23 32 45 54 67 76 89
```
````

Keep diagram borders, connecting arrows, tree branches, calculation separators, and byte brackets: they convey relationships and are part of the example. For a supported diagram, add `layout="diagram" diagram="…"` to its existing `.text` fence instead of deleting those lines or shrinking the font. The build converts padded ASCII geometry into responsive CSS borders and connected rows. The original fence remains the single authored source; **Copy** returns its original text, and **Copy page** includes the unchanged diagram. There is one visible representation, no hidden duplicate listing, and no JavaScript renderer.

Supported diagram types are `boxes` (closed Setup/Vault-style boxes joined by an explicit TARGET), `sequence` (steps separated by `│` and `▼`), `tree` (indented `├──`/`└──` branches), `calculation` (aligned operands, dashed rule, result), `bytes` (bracketed byte rows), and `halves` (two labeled byte groups). These are deliberately narrow patterns, not a general ASCII-art parser. Invalid structural input fails the build rather than silently discarding it. Diagram labels use the site's 14px/20px reading font; byte cells and numeric values retain the monospace font. Short plain-text examples such as the accepted Left/Right shifts remain unchanged.

All examples stay expanded, readable without JavaScript, and printable in full. Unsupported ASCII art still preserves its source columns inside a horizontal scroller; do not opt it into a responsive pattern unless the visible relationships and all content have regression coverage. Avoid tiny type, vertical clipping, or flattening a connected diagram into an unconnected list.

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
