---
title: Tools & workflow
description: Write in Markdown, preview locally, and publish through GitHub Pages.
---

# Tools & workflow

This site uses **MkDocs** with a custom GitBook-style theme. Content lives in plain Markdown, and the frontend uses locally hosted fonts, CSS, and a small amount of JavaScript. No Node.js build is required.

## Preview locally

Install Python 3.11 or later and run these commands from the repository root.

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m mkdocs serve
```

On macOS or Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m mkdocs serve
```

Open the local URL printed by MkDocs. Changes to Markdown or the theme reload the preview.

## Add a page

1. Create a `.md` file under `docs/`.
2. Add a title and optional description in YAML front matter.
3. Register the page under `nav` in `mkdocs.yml`.
4. Link to other pages using relative `.md` paths.
5. Preview the page before committing.

```yaml
---
title: A new note
description: What the reader will learn.
---
```

Use level-two and level-three headings for the page outline. Fenced code blocks can specify a language such as `python`, `bash`, or `json` for syntax highlighting.

## Useful writing features

### Callouts

MkDocs admonitions provide notes, tips, and warnings.

```markdown
!!! note "A useful observation"
    Explain the detail here. Indent the callout body by four spaces.
```

### Code and tables

The theme adds copy controls to highlighted code blocks. Wide code and tables scroll inside their own containers instead of widening the entire page.

### Search and navigation

Search indexes the full content at build time. Open it with **Ctrl K** on Windows/Linux or **⌘ K** on macOS. Use the arrow keys to choose a result and Enter to open it.

Use the sidebar controls to choose light, dark, or system appearance. The default is dark, matching the visual reference.

## Build and validate

```bash
python -m mkdocs build --strict
python -m unittest discover -s tests -v
```

These commands assume your virtual environment is activated. Otherwise use its full Python path, as in the preview commands.

Browser tests have additional development dependencies; the repository README includes the full setup. Build output is written to `site/` and is not committed.

## Publish

The included GitHub Actions workflow builds the site on pushes to `main`. In the repository's **Settings → Pages**, select **GitHub Actions** as the source if it has not already been enabled.

The configured URL is:

[evilzcoder.github.io/kokogray-lab](https://evilzcoder.github.io/kokogray-lab/)

!!! note "Deployment status"
    A configured URL is not proof that deployment has completed. Check the repository's Actions tab for the actual deployment result.

## Before pushing a writeup

- Replace all unfinished placeholders.
- Redact secrets, private information, and live session identifiers.
- Respect challenge embargoes and event rules.
- Check internal links and image paths.
- Include sources and defensive lessons.
