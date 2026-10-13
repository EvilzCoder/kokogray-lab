---
title: Writeup template
description: A starting point for a clear, evidence-led CTF writeup.
---

# Writeup template

!!! note "Template, not a completed challenge"
    Replace every placeholder with your own observations. There is no completed challenge or real flag on this page.

## Challenge description

Record the challenge prompt in your own words, along with the event, category, objective, and authorized scope.

| Field | Your notes |
| --- | --- |
| Event | `<event name>` |
| Challenge | `<challenge name>` |
| Category | `<web / cloud / crypto / forensics / other>` |
| Environment | `<local lab or challenge instance>` |
| Objective | `<success condition>` |

## Solution overview

Summarize the key idea in a few sentences. Explain which assumption was incorrect and which observation led you to investigate it.

A reader should understand the direction of the solution before seeing individual steps.

## Initial analysis

### Architecture overview

Describe the components, the identities involved, and the data flow. Identify which boundaries are meant to separate users, services, or environments.

```text
Participant → Challenge application → Lab service
                        ↓
                  Challenge data
```

### Important observations

Separate what you verified from what you inferred. Include the smallest relevant excerpt of a response, log, or supplied source file. Redact tokens and private information.

## Verification

### Step 1 — Establish the baseline

Describe the expected behavior and the input that demonstrates it. Mention any local setup needed to reproduce the result.

### Step 2 — Test the hypothesis

Explain the controlled change, why it is relevant, and the observation that supports or disproves the hypothesis. Keep all testing inside the permitted environment.

### Step 3 — Confirm the result

Show the challenge's success condition, or explain why the evidence is not yet conclusive. Do not invent output for a step you did not run.

## Outcome

Record the actual result. If event rules allow a flag to be shared, decide whether publishing it adds value; otherwise use `<REDACTED_FLAG>`.

## Defensive lessons

- What control would prevent this behavior?
- Where should that control be enforced?
- What test would catch a regression?
- What logs would help someone detect the issue?

## References

Link the official documentation and resources that informed your reasoning. Credit the original source of any quoted text or adapted material.

## Copyable starting point

Create a page under `docs/2026/<event>/<challenge>.md` using this outline, then register it in `mkdocs.yml`.

```markdown
---
title: Your challenge
description: One sentence about the problem and the lesson.
---

# Your challenge

## Challenge description

## Solution overview

## Initial analysis

### Architecture overview

### Important observations

## Verification

## Outcome

## Defensive lessons

## References
```
