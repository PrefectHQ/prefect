---
name: agents-md-sync
description: Analyze code changes on the current branch and recommend updates to AGENTS.md files that have become stale. Use this skill before creating a PR, when the user asks to check AGENTS.md freshness, or when preparing an AGENTS.md update after a PR merges to main. Trigger whenever the user mentions syncing, updating, or checking AGENTS.md files, or when they're about to create a PR that touches code structure (new modules, renamed directories, changed commands, modified architecture).
---

# AGENTS.md Sync

Detect when code changes make AGENTS.md files stale and produce a report with specific recommendations.

## When to use

- Before creating a PR — check if the branch's changes warrant AGENTS.md updates
- After a PR merges to main — audit whether merged changes left AGENTS.md files outdated
- On explicit request — "are the AGENTS.md files up to date?"

## Workflow

### 1. Determine the diff

Figure out what changed relative to the base branch. The approach depends on context:

- **On a feature branch (pre-PR):** diff against main
  ```bash
  git diff main...HEAD --name-status
  git diff main...HEAD
  ```
- **After a merge to main:** the user should specify which PR or commit range to audit. Use the merge commit or PR number to get the diff:
  ```bash
  gh pr diff <number>
  ```
- **Explicit check:** if the user just says "check AGENTS.md", diff against main

### 2. Map changes to AGENTS.md territories

Each AGENTS.md file "owns" the directory it lives in and all subdirectories (unless a child directory has its own AGENTS.md). Build a list of which AGENTS.md files are relevant by walking up from each changed file to find the nearest AGENTS.md.

Example: a change to `src/prefect/server/api/flows.py` is owned by `src/prefect/server/AGENTS.md` (if it exists), otherwise `src/prefect/AGENTS.md`.

Only analyze AGENTS.md files that have at least one changed file in their territory. Also include parent AGENTS.md files if structural changes (new directories, moved files) affect the directory tree they document.

### 3. Check for missing AGENTS.md files

Before analyzing existing AGENTS.md files, check whether any changed directories *should* have their own AGENTS.md but don't. This is especially important when:

- New files are added to a directory that has no AGENTS.md and is growing in complexity
- A directory accumulates enough distinct modules or patterns that its parent AGENTS.md can't adequately describe it
- Sibling directories at the same level already have their own AGENTS.md files

Look at the directories containing changed files. For each one that lacks an AGENTS.md, check:
1. How many files does it contain? (A directory with 5+ files likely benefits from its own AGENTS.md)
2. Do sibling directories have AGENTS.md files? (Consistency matters — if `server/` has one, `utilities/` probably should too)
3. Are there non-obvious patterns or conventions in this directory that a developer would need to know?

If any of these conditions are met, recommend creating a new AGENTS.md. The initial content can be conservative — it only needs to cover what's relevant right now, not be exhaustive. Even a small AGENTS.md that describes a few key modules is better than none, because it establishes the file for future updates to build on.

This check is important and should not be skipped due to general conservatism about existing AGENTS.md files. The bar for suggesting a *new* AGENTS.md is lower than the bar for modifying an existing one — creating a new file carries no risk of breaking existing documentation.

A common trap: dismissing a missing AGENTS.md because the gap is "pre-existing" or "unrelated to this PR." The PR doesn't need to have *caused* the gap — it just needs to have *surfaced* it by touching files in that directory. If a directory meets the criteria above (5+ files, siblings have AGENTS.md), recommend creating one. The suggested content should focus on what's relevant to the current changes, not attempt to be exhaustive.

Another trap: concluding that a directory is "just private helpers" or "internal utilities" and therefore doesn't need an AGENTS.md. Directories with many files benefit from an AGENTS.md precisely *because* their contents are non-obvious — a developer landing in a 30-file utilities directory benefits from knowing what's there and what conventions to follow. Don't let the "private/internal" nature of a directory be a reason to skip recommending an AGENTS.md.

### 4. Analyze each relevant AGENTS.md

For each AGENTS.md in scope, read it fully, then compare its claims against the diff. Look for these categories of staleness:

**Structural drift** — the AGENTS.md describes a directory layout, file list, or module structure that no longer matches reality:
- Directories or files added/removed/renamed but not reflected in documented trees
- New modules or packages not mentioned
- Removed components still listed

**Command drift** — documented commands that may no longer work or are incomplete:
- Build/test/run commands referencing changed entry points
- New tooling or scripts not mentioned

**Convention drift** — code patterns or conventions described in AGENTS.md that the diff contradicts:
- New patterns established by the changes that aren't documented
- Existing conventions the changes deprecate or replace

**Description drift** — prose descriptions that no longer accurately characterize the code:
- Component descriptions that miss new responsibilities
- Architecture notes that don't reflect refactoring

For each finding, check whether it's actually stale — read the current state of the filesystem (not just the diff) to confirm. A diff showing a new file doesn't mean AGENTS.md is wrong if AGENTS.md intentionally omits that level of detail.

### 5. Produce the report

Output a concise report grouped by AGENTS.md file. For each file, list findings with:
- **What's stale** — the specific line or section
- **Why** — which change caused it
- **Suggested fix** — the concrete text to add, remove, or change

Format:

```markdown
## AGENTS.md Sync Report

### New AGENTS.md recommended: `src/prefect/utilities/`

This directory contains 12 modules but has no AGENTS.md. Sibling directories (`server/`, `settings/`) each have one. Suggested outline:
- Purpose of the utilities package
- Key modules and what they provide
- Conventions (e.g., private vs public utilities)

### `src/prefect/server/AGENTS.md`

1. **[Structural]** New directory `src/prefect/server/events/` not listed in directory structure
   - Caused by: `src/prefect/server/events/` added in this branch
   - Suggested fix: Add `events/` to the directory listing with description

2. **[Command]** Test command references `pytest tests/server/` but new test file uses different path
   - Caused by: test reorganization in `tests/server/`
   - Suggested fix: Update command to `pytest tests/server/events/`

### `./AGENTS.md` (root)
No changes needed.
```

If nothing is stale, say so clearly — don't manufacture findings.

### 6. Offer next steps

After presenting the report, offer:
- **Apply fixes** — make the suggested edits directly
- **Create a follow-up PR** — if this is a post-merge audit, offer to create a branch and PR with just the AGENTS.md updates
- **Skip** — if the changes are minor or the user disagrees with the suggestions

## Important guidelines

- Be conservative — only flag things that are genuinely wrong or missing. AGENTS.md files are intentionally concise and don't need to document every file.
- Don't suggest adding content that's obvious from the code itself. AGENTS.md captures non-obvious patterns, gotchas, and high-level structure.
- Don't suggest stylistic rewrites. Focus on factual accuracy.
- When in doubt about whether something is stale, check the filesystem to confirm rather than guessing from the diff alone.
- Respect the existing level of detail in each AGENTS.md. If a file only lists top-level directories, don't suggest adding individual files.
