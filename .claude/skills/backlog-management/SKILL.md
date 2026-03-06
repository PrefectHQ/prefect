---
name: backlog-management
description: Manage open-source GitHub issue backlogs (especially PrefectHQ/prefect) in batches. Use for backlog cleanup days, stale review, duplicate pruning, missing-info follow-up, and prioritized queue curation across many open issues.
---

# Backlog Management

Use this skill for batch backlog work, not for deep triage of a single new issue.

## Scope

- Open-source repositories only.
- Use public, contributor-friendly language.
- Do not reference internal plans or private project context.

## Default Mode

- Work in batches of 25-100 issues.
- Start in read-only mode and propose actions first.
- Apply edits only after approval unless explicitly asked to execute immediately.

## Workflow

1. Build a candidate batch.
2. Assign one primary action per issue.
3. Draft concise comments where needed.
4. Apply approved edits.
5. Report outcomes with counts and issue links.

## Candidate Queries (PrefectHQ/prefect)

Use focused searches:

```bash
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue no:assignee sort:updated-asc" --limit 100
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue label:status:stale sort:updated-asc" --limit 100
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue label:bug -label:needs:mre sort:updated-asc" --limit 100
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue label:needs:details sort:updated-asc" --limit 100
```

## Action Set

Choose exactly one primary action per issue:

- `keep-open`: still actionable, no immediate label change needed
- `needs:details`: missing context blocks progress
- `needs:mre`: bug report lacks minimal reproducible example
- `status:stale`: inactive and low-signal, not exempt
- `close-duplicate`: close with canonical issue link
- `close-not-planned`: close with concise reason when clearly out of scope or no longer actionable

## Real Labels (PrefectHQ/prefect)

Only use labels that exist in this repo. Key labels for backlog work include:

- `needs:details`
- `needs:mre`
- `status:stale`
- `needs:triage`
- `question`
- `bug`
- `enhancement`
- `good first issue`
- `blocked`
- `status:exempt`

Verify labels before applying changes:

```bash
gh label list --repo PrefectHQ/prefect --limit 300
```

## Comment Templates

Missing details:

```text
Thanks for opening this. We need a bit more detail before we can move this forward:
- expected behavior
- actual behavior
- exact steps to reproduce
```

Missing MRE:

```text
Thanks for the report. Please share:
1) a minimal reproducible code sample,
2) full traceback/error text,
3) output of `prefect version`.
```

Duplicate close:

```text
Closing as a duplicate of #<issue-number> so discussion stays in one place.
If this is materially different, comment with details and we can reopen.
```

## Guardrails

- Do not close issues only because they are old.
- Do not mark as stale when clear maintainer/reporter activity is recent.
- Do not apply conflicting labels.
- Do not over-explain; keep comments short and specific.
