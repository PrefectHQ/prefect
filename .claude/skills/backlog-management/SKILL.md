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
3. Deep-dive only close candidates.
4. Draft concise comments where needed.
5. Apply approved edits.
6. Report outcomes with counts and issue links.

## Two-Pass Review Depth

Use two passes by default:

- Pass 1 (sweep): classify quickly across the full batch.
- Pass 2 (dig-in): re-review only `close-not-planned` and `close-duplicate` candidates.

Do not finalize close actions from Pass 1 alone.

For Pass 2, require explicit evidence:

- architecture/status check against current Prefect behavior
- concrete links (issue comments, PRs, release notes, docs, code)
- counterevidence (why issue might still be valid)
- confidence (`low`, `medium`, `high`)

If evidence is weak or mixed, downgrade close to:

- `needs:details`
- `needs:mre`
- `status:stale`
- `keep-open`

UI replatform exception:

- Prefect currently has both legacy UI code (`ui/`) and the React replatform (`ui-v2/`).
- For UI issues that appear tied to legacy UI behavior, do not close based only on age/architecture drift until `ui-v2` is GA.
- Before proposing close, check whether the reported behavior is represented in `ui/`, `ui-v2/`, or both.
- Default action before GA is `keep-open` (or `status:stale` only if explicitly desired by maintainers).

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

## Deep-Dive Output Format

For every close candidate, produce this mini-record before execution:

- `issue`: number + title
- `claim_to_verify`: why it appears closable
- `current_state_check`: does claim still hold today?
- `evidence_links`: specific references
- `counterevidence`: any signal to keep open
- `recommended_action`: final action after deep-dive
- `confidence`: low/medium/high

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
gh label list --repo PrefectHQ/prefect --limit 30
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
If this is materially different, tag me and comment with details; we can reopen.
```

## Guardrails

- Do not close issues only because they are old.
- Do not mark as stale when clear maintainer/reporter activity is recent.
- Do not apply conflicting labels.
- Do not over-explain; keep comments short and specific.
- Do not close legacy-UI issues before `ui-v2` GA unless there is a strong non-UI reason (for example, duplicate with active canonical issue).
