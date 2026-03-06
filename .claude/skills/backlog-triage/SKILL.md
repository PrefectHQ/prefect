---
name: backlog-triage
description: Manage open-source GitHub issue backlogs and triage individual issues, especially in PrefectHQ/prefect. Use for backlog curation (batch prioritization, stale review, duplicate pruning) and for issue triage (quality checks, missing reproduction requests, label decisions, and clear next-step comments).
---

# Backlog and Triage

Backlog management and issue triage are related but different.

Use this skill with explicit mode selection:

- Backlog management: curate a queue of many issues.
- Issue triage: make a decision on a specific issue.

## Scope

This skill is for open-source repositories. Do not rely on private or internal project guidance.

## Open-Source Dynamics

Backlog triage in public repos is not just queue cleanup. It is also community guidance.

Prefer decisions that increase contributor success:

- Convert vague reports into actionable reports when possible.
- Explain triage decisions publicly and respectfully.
- Ask for specific follow-up data instead of generic "need more info."
- Use labels and comments as transparent signals for maintainers and contributors.
- Avoid references to private project plans, private constraints, or internal-only processes.

## Quick Start

Start with a read-only backlog scan using focused queries, then produce an action plan:

- `keep-open` with rationale
- `needs:details` with specific follow-up ask
- `needs:mre` when reproduction is missing
- `status:stale` when issue is inactive and low-signal
- `close` (duplicate, resolved, invalid, out-of-scope)

## Workflow

### Mode A: Backlog management (batch)

Goal: improve queue health and maintainer focus for a batch (for example 25-100 issues).

1. Build candidate queues with targeted searches.
2. Group by action category (stale candidate, duplicate candidate, needs detail, keep open).
3. Propose batched actions with concise per-issue rationale.
4. Apply only approved actions.
5. Report counts and changed issue list.

### Mode B: Issue triage (single issue)

Goal: unblock one issue with the minimum clear next step.

1. Read the issue body and recent comments.
2. Check template completeness and repro quality.
3. Choose one primary next action.
4. Leave a high-signal comment and/or label update.
5. Record the decision rationale.

### 1) Build candidate queues

Use focused `gh issue list` queries instead of scanning the entire backlog.

Core queues:

- `is:open is:issue label:needs:triage sort:updated-asc`
- `is:open is:issue no:assignee sort:updated-asc`
- `is:open is:issue label:status:stale sort:updated-asc`
- `is:open is:issue label:bug -label:needs:mre sort:updated-asc`

### 2) Classify quickly

For each issue, classify:

- Bug report quality (clear summary, reproducible steps/code, version info).
- Enhancement quality (current behavior, proposed behavior, concrete use case).
- Whether question/support belongs in Discussions instead of Issues.

### 3) Choose one primary action

Pick one dominant action per issue. Avoid piling on conflicting labels.

Examples:

- Missing repro details for a bug: `needs:mre`
- Missing contextual info: `needs:details`
- Clear duplicate: close with canonical issue link
- Inactive and low-signal: `status:stale`
- Legitimate, actionable, but undecided: keep `needs:triage`

### 4) Write high-signal comments

Comments should be short, specific, and unblock the next step.

Good comment characteristics:

- Requests exactly what is missing.
- Gives copy/paste command(s) when relevant.
- States what will happen next if no response is provided.
- Uses public, contributor-friendly language.

See [prefect-triage-reference.md](references/prefect-triage-reference.md) for templates.

### 5) Apply changes safely

Default mode is dry-run proposal. If applying:

- Make minimal edits (labels/comments/state only).
- Do not change issue intent.
- Record issue number, action, and reason.

### 6) Report outcomes

Always end with:

- Counts by action type
- List of changed issues
- Follow-up batch suggestions (next 20-50 issues)

## Repo Conventions (PrefectHQ/prefect)

Key signals from current repo configuration:

- Bug template expects repro details and `prefect version` output.
- Enhancement template starts with `needs:triage`.
- Stale automation closes issues 7 days after `status:stale`.
- Exempt issue labels from stale closure include:
  - `status:exempt`
  - `needs:attention`
  - `needs:triage`
  - `blocked`

Verify labels before applying changes:

```bash
gh label list --repo PrefectHQ/prefect --limit 200
```

## Guardrails

- Do not close issues only because they are old.
- Do not assume “cannot reproduce” without asking for missing details first.
- Do not mark issues stale if they have active owner signals or exempt labels.
- Do not invent repo policies; cite observable evidence from issue content, templates, and labels.
- Do not cite or imply private/internal guidance in public triage comments.
