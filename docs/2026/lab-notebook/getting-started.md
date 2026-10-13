---
title: Getting started
description: A repeatable workflow for the first hour of a new challenge.
---

# Getting started

A little structure makes investigation easier. Keep the scope, your observations, and your evidence in one place so the final writeup is a record of reasoning rather than a reconstruction from memory.

## Before you begin

Read the challenge rules and record the assets you are allowed to test. A domain or service mentioned in challenge material is not automatically in scope.

!!! warning "Check the boundaries"
    Use challenge-provided environments or your own local lab. Do not reuse techniques against unrelated services, and stop if the environment exposes real customer data.

### Create a workspace

Keep original inputs separate from working files and screenshots. The following commands create only local directories.

```bash
mkdir -p my-challenge/{originals,working,evidence,notes}
```

| Directory | Purpose |
| --- | --- |
| `originals/` | Untouched copies of supplied files |
| `working/` | Scratch files and experiments |
| `evidence/` | Redacted screenshots and relevant output |
| `notes/` | Timeline, hypotheses, and draft explanation |

### Record the starting point

Write down the challenge name, category, objective, rules, and the date of the exercise. Record tool versions when behavior depends on them.

```text
Challenge: <name>
Category: <category>
Scope: <explicitly permitted assets>
Goal: <what success means>
Environment: <local or challenge-provided>
```

## Observe before changing anything

Read the description and supplied source code. Map the components and the data that moves between them. Identify what the user controls, what the application trusts, and where access checks happen.

Keep a short evidence log:

- **Observation:** what you can directly see.
- **Hypothesis:** an explanation that could be wrong.
- **Check:** the smallest permitted action that distinguishes the alternatives.
- **Result:** what happened, including failed assumptions.

## Keep experiments reproducible

Change one variable at a time. Save the relevant inputs and outputs, but keep secrets out of your notes and screenshots. Use placeholders such as `<LAB_TOKEN>` when explaining a step.

When a result looks surprising, repeat the minimum safe check. Distinguish an actual finding from cached output, a local configuration difference, or an expired session.

## Turn notes into a writeup

Use the [writeup template](writeup-template.md) once you can explain the full chain. The finished page should let a reader follow the reasoning without access to private credentials.

1. State the objective and scope.
2. Explain the system and the important assumption.
3. Show only the evidence needed to support the result.
4. Include the defensive fix and any uncertainty.
5. Remove secrets and respect event publication rules.

## After the challenge

Delete temporary credentials, stop local services, and remove any resources you created in your own cloud account. Move reusable lessons into the [knowledge base](../../knowledge-base/cloud-security.md).
