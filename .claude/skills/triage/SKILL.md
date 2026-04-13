---
name: triage
description: Surface what needs attention right now — open PRs awaiting review, new issues, active discussions, merge-ready work. Use for Monday catchups, returning from time off, or anytime you need a status check.
---

# Triage

Answer "what needs my attention right now?" by scanning open PRs, recent issues, and active discussions. Present a prioritized, actionable summary.

## Scope

- Default repo: `PrefectHQ/prefect`. Override via `$ARGUMENTS` (e.g., `PrefectHQ/prefect-aws` or a time range like `since April 1`).
- Read-only — never comment, merge, label, or modify anything.

## Workflow

### 1. Gather state

Query open and recently-created items. Adjust the time window if the user specifies one, otherwise use reasonable defaults (open PRs have no time cutoff; new issues default to ~3 days).

```bash
# Open PRs needing attention
gh pr list --repo <repo> --search "is:pr is:open sort:updated-desc" --limit 30

# Recently created issues
gh issue list --repo <repo> --search "is:issue is:open sort:created-desc" --limit 20

# Recently merged PRs (for context on what shipped)
gh pr list --repo <repo> --search "is:pr is:merged merged:>=<date> sort:updated-desc" --limit 20
```

### 2. Enrich with review status and comments

For every open PR, fetch approvals, review state, and comment threads. For issues with activity, read comments. This is the step that makes triage useful — a bare list of titles is not actionable.

```bash
gh pr view <number> --json reviews,comments,state,reviewDecision
gh pr view <number> --comments
gh issue view <number> --comments
```

Skip bot noise when summarizing (codspeed, dependabot, stale bot, AGENTS.md auto-updates).

### 3. Present by action needed

Group items into buckets:

- **ready to merge** — approved, CI green, no blockers
- **needs review** — no reviews yet or review requested
- **needs attention** — unresolved comments, changes requested, CI failing, or active discussion
- **new issues** — recently opened, noting labels and whether anyone has responded
- **recently shipped** — notable merged PRs (not bot/housekeeping)
- **housekeeping** — dependabot bumps, auto-updates, bot PRs (one-line summary count)

For each item include: number, title, author, and the relevant context (approval status, reviewer names, comment gist, labels). Add a one-line description if the title is ambiguous.

## Guardrails

- Do not comment on, merge, label, or modify anything
- Do not speculate about priority — present facts, let the user decide what to act on
- If there's nothing actionable, say so
