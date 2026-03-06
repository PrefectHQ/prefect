# Prefect Triage Reference

This reference captures open-source triage signals for `PrefectHQ/prefect`.

## Public triage principles

- Optimize for clarity and fairness in public threads.
- Prefer "ask and unblock" over "close and move on" when effort to unblock is low.
- Make next steps explicit so reporters know how to get back to active triage.
- Keep comments factual; avoid private roadmap or internal prioritization language.

## Label cues

Common issue labels relevant to backlog triage:

- `needs:triage` - new enhancement requests awaiting maintainer triage
- `needs:details` - missing context from reporter
- `needs:mre` - missing minimal reproducible example for a bug
- `status:stale` - marked inactive; stale workflow can auto-close
- `status:exempt` - excluded from stale closure
- `blocked` - excluded from stale closure
- `question` - clarification request; may belong in Discussions
- `bug`, `enhancement`, `docs`, `api`, `cli`, `ui`, `integrations` - topical routing

## Decision matrix

Use this quick matrix per issue:

1. If duplicate with strong match:
Action: close as duplicate
Reason: de-duplicate maintainer work and centralize context

2. If bug report lacks repro/version info:
Action: add `needs:mre` or `needs:details` and request specifics
Reason: cannot validate or fix without reproduction context

3. If enhancement request is unclear:
Action: keep/add `needs:triage`, ask clarifying questions
Reason: preserve request but force decision-ready framing

4. If support-style question:
Action: route to Discussions, optionally close issue
Reason: keep issue tracker focused on actionable defects/features

5. If inactive with no owner signals and not exempt:
Action: add `status:stale` (or keep if already present)
Reason: align with stale workflow and reduce backlog noise

## Comment templates

Template: missing reproduction details

```text
Thanks for the report. We need a minimal reproducible example to investigate.

Please share:
1) a minimal code sample we can run,
2) full traceback/error text (not screenshots),
3) output of `prefect version`.

Once we have that, we can triage this quickly.
```

Template: missing general details

```text
Thanks for opening this. We need a bit more detail before we can triage:
- expected behavior
- actual behavior
- exact steps to reproduce

If you can share those, we can move this forward.
```

Template: duplicate closure

```text
Closing as a duplicate of #<issue-number> so discussion and implementation stay in one place.
If this issue captures a distinct case, comment with details and we can reopen.
```

Template: stale notice

```text
Marking as inactive for now. Without additional activity, this may be automatically closed.
If this is still relevant, add an update and we will re-triage.
```

## Useful queries

Needs triage:

```bash
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue label:needs:triage sort:updated-asc" --limit 200
```

Old open issues with no assignee:

```bash
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue no:assignee sort:updated-asc" --limit 200
```

Stale-labeled issues:

```bash
gh issue list --repo PrefectHQ/prefect --search "is:open is:issue label:status:stale sort:updated-asc" --limit 200
```

## Applying changes

Add labels:

```bash
gh issue edit <number> --repo PrefectHQ/prefect --add-label "needs:mre"
```

Add comment:

```bash
gh issue comment <number> --repo PrefectHQ/prefect --body "<comment text>"
```

Close issue:

```bash
gh issue close <number> --repo PrefectHQ/prefect --reason "not planned"
```
