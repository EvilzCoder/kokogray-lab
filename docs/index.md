---
title: Welcome
description: CTF writeups, cloud security notes, and lessons from the lab.
---

# Welcome

Welcome to **Kokogray Lab** — a notebook for understanding how systems work, where their assumptions break, and how to make them safer.

This is a place for reproducible notes, not just the final flag. Start with the lab notebook, explore a topic, or use the writeup template to document your next challenge.

!!! note "The lab is ready"
    This is a new notebook. The pages below are original starter guides and templates, not claims of completed CTF challenges. Add your own writeups as you go.

## Explore the lab

<div class="doc-cards" markdown="1">

[**Lab notebook →**<span>Set up a workspace and build a repeatable approach to each challenge.</span>](2026/lab-notebook/getting-started.md){ .doc-card }

[**Writeup template →**<span>A clean structure for your findings, evidence, and lessons learned.</span>](2026/lab-notebook/writeup-template.md){ .doc-card }

[**Cloud security →**<span>Identity, permissions, storage, and trust boundaries.</span>](knowledge-base/cloud-security.md){ .doc-card }

[**Web security →**<span>Requests, sessions, authorization, and careful testing.</span>](knowledge-base/web-security.md){ .doc-card }

</div>

## How the notebook is organized

| Section | What belongs here |
| --- | --- |
| **2026 / Lab notebook** | Challenge notes, experiments, and writeups organized by event |
| **Knowledge base** | Reusable concepts and checklists that apply across challenges |
| **Tools & workflow** | Local setup, evidence handling, and publishing |

Each writeup should explain the starting point, the important observation, the verification, and the defensive lesson. Include the dead ends when they help explain the result.

## A good writeup answers

1. **What was the goal?** State the challenge objective and the permitted scope.
2. **What did you observe?** Separate facts from hypotheses.
3. **Why did it work?** Explain the behavior, not just the command.
4. **How can it be fixed?** End with the control that would have prevented the issue.

> The useful part of a writeup is the reasoning someone else can follow.

## Start writing

Create a Markdown file under `docs/2026/`, then add it to the navigation in `mkdocs.yml`. The site generates the page outline, search index, and previous/next navigation for you.

```yaml
nav:
  - Welcome: index.md
  - '2026':
      - Your event:
          - Your challenge: 2026/your-event/your-challenge.md
```

For a ready-to-fill structure, open the [writeup template](2026/lab-notebook/writeup-template.md). For local preview and deployment instructions, see [Tools & workflow](knowledge-base/tools-and-workflow.md).

!!! tip "Keep it responsible"
    Work only in systems you own or are explicitly authorized to test. Remove live credentials, personal information, and out-of-scope targets before publishing.
