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
1. **Semantic boundary**: Does this directory represent a distinct responsibility shift? (e.g., a utilities package vs. a core engine — different concerns warrant separate nodes)
2. **Scale**: How many files does it contain? (A directory with 5+ files likely benefits from its own AGENTS.md)
3. **Sibling consistency**: Do sibling directories have AGENTS.md files? (If `server/` has one, `utilities/` probably should too)
4. **Hidden knowledge**: Are there non-obvious patterns or conventions in this directory that a developer would need to know?

These checks are a hard decision rule. If a directory has 5+ files AND sibling directories have AGENTS.md files, the report MUST recommend creating one. List it under "New AGENTS.md recommended" in the report, not as a "candidate" or "future consideration." The recommendation is actionable and immediate — the user will decide whether to act on it.

Do not soften, defer, or hedge this recommendation. Do not say "worth noting for the future," "could be addressed separately," or "independent of this PR." If the criteria are met, recommend it. Period. The nature of the code (utilities, helpers, private modules, etc.) is irrelevant to this decision.

When recommending a new AGENTS.md, use the Explore agent to read the directory's code and draft the file using this template:

```markdown
# <Module Name>

<One-sentence purpose statement.>

## Purpose & Scope

What this module does. Explicit responsibility boundaries.
What it does NOT do (prevents scope creep).

## Entry Points & Contracts

Key APIs, functions, classes that external consumers use.
Input/output contracts. Invariants that must hold.

## Usage Patterns

Canonical examples of correct usage.
"If you need to do X, here's how."

## Anti-Patterns

What NOT to do. Common mistakes. Each should be a real mistake, not hypothetical.

## Pitfalls

Non-obvious gotchas. Implicit assumptions.
"You'd think X, but actually Y because Z."
```

The initial content can be conservative — focus on what the code reveals and what's relevant to the current changes. Not every section needs to be filled. Mark gaps where you suspect tribal knowledge is needed but can't determine it from code alone with `[ASK: specific question]` markers so the user can fill them in. Even a small AGENTS.md is better than none, because it establishes the file for future updates to build on.

This check is important and should not be skipped due to general conservatism about existing AGENTS.md files. The bar for suggesting a *new* AGENTS.md is lower than the bar for modifying an existing one — creating a new file carries no risk of breaking existing documentation.

A common trap: dismissing a missing AGENTS.md because the gap is "pre-existing" or "unrelated to this PR." The PR doesn't need to have *caused* the gap — it just needs to have *surfaced* it by touching files in that directory. If a directory meets the criteria above (5+ files, siblings have AGENTS.md), recommend creating one. The suggested content should focus on what's relevant to the current changes, not attempt to be exhaustive.

Another trap: concluding that a directory is "just private helpers" or "internal utilities" and therefore doesn't need an AGENTS.md. Directories with many files benefit from an AGENTS.md precisely *because* their contents are non-obvious — a developer landing in a 30-file utilities directory benefits from knowing what's there and what conventions to follow. Don't let the "private/internal" nature of a directory be a reason to skip recommending an AGENTS.md.

### 4. Analyze each relevant AGENTS.md

AGENTS.md files form a hierarchy — when an agent loads any file, all ancestor files load too, creating a T-shaped view (broad context at the top, specific detail where the agent works). This has two implications for the sync check:

**Least common ancestor rule**: Shared knowledge should live at the shallowest AGENTS.md that covers all paths needing it. If the same fact appears in multiple sibling AGENTS.md files, flag it — it should move to their parent. Conversely, if a parent AGENTS.md contains detail that only applies to one child directory, suggest moving it down.

**Upward propagation**: When a child AGENTS.md changes (or a new one is created), check whether the parent needs updating — either to add a cross-reference to the new child, or to re-summarize what the child directory does. Parent nodes should summarize their children's responsibilities, not duplicate their details.

For each AGENTS.md in scope, read it fully, then compare its claims against the diff **and** the current source code. Look for these categories of issues:

**Accuracy** — claims in AGENTS.md that don't match the actual code, regardless of whether the diff caused the discrepancy:
- Described behaviors that don't match what the code actually does (e.g., "renews at 75% of duration" when it actually renews immediately then sleeps 75%)
- Function signatures or parameters listed that are wrong or incomplete
- Responsibilities attributed to the wrong layer or module
- Error handling or failure modes described incorrectly

For claims that are verifiable (specific behaviors, function signatures, which module does what), read the source file and confirm. Don't trust that existing AGENTS.md content was ever correct — it may have been wrong from the start.

**Signal density** — content that duplicates what's discoverable from code rather than surfacing hidden knowledge:
- Full function signatures that just repeat the code (the *contracts* and *gotchas* around those functions are the high-signal parts)
- Trivial usage examples that match what's in docstrings or is obvious from the API
- File-by-file directory listings that `ls` would show — the *layering concept* or *architectural invariant* matters, not the enumeration
- Content that a developer would learn in 30 seconds of reading the source

AGENTS.md should capture what's *not* visible in the code: invariants, hidden contracts, non-obvious failure modes, things that look one way but behave another.

**Missing invariants** — implicit contracts the code relies on that aren't documented:
- Parallel implementations that must stay in sync (e.g., sync and async versions of the same module)
- Ordering requirements or sequencing constraints
- Singleton behaviors or shared mutable state
- Cleanup responsibilities and what happens when they're skipped
- "This looks stateless but actually depends on X"

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

**Hierarchy drift** — content living at the wrong level in the AGENTS.md tree:
- Knowledge duplicated across sibling AGENTS.md files that should be in their parent (least common ancestor)
- Parent-level detail that only applies to one child directory
- Parent summaries of child directories that no longer match after changes

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

1. **[Accuracy]** Lease renewal described as "renews at 75% of duration" but code renews immediately then sleeps 75%
   - Caused by: incorrect from initial creation
   - Suggested fix: "renews immediately on entry, then sleeps for 75% of `lease_duration` between renewals"

2. **[Signal density]** Full function signatures duplicate the code — remove parameter lists, keep contracts
   - Suggested fix: Replace `concurrency(names, occupy=1, ...)` with `concurrency()` and describe the non-obvious behaviors instead

3. **[Missing invariant]** Sync and async implementations must stay in lockstep but this isn't documented
   - Suggested fix: Add "Any behavior change to `_asyncio.py` must be mirrored in `_sync.py`"

4. **[Structural]** New directory `src/prefect/server/events/` not listed in directory structure
   - Caused by: `src/prefect/server/events/` added in this branch
   - Suggested fix: Add `events/` to the directory listing with description

### `./AGENTS.md` (root)
No changes needed.
```

If nothing is stale, say so clearly — don't manufacture findings.

### 6. Offer next steps

After presenting the report, offer:
- **Apply fixes** — make the suggested edits directly
- **Create a follow-up PR** — if this is a post-merge audit, offer to create a branch and PR with just the AGENTS.md updates
- **Skip** — if the changes are minor or the user disagrees with the suggestions

## Reactive mode

Outside of diff-driven analysis, if during normal development you discover missing context that should be in an AGENTS.md, propose an addition. Signs of missing context:

- You had to read 5+ files to understand a pattern that could be a one-liner in AGENTS.md
- You hit a non-obvious error because of an undocumented constraint
- You discovered a cross-system dependency that isn't mentioned anywhere
- A code review caught something that AGENTS.md should have prevented

Propose additions like this:
```
I discovered that [finding]. This isn't in [path]/AGENTS.md.

Proposed addition to the [section] section:
> [concrete text to add]

Should I add this?
```

## Quality checks for new or updated AGENTS.md content

- **Compression**: Can any section be shorter without losing information?
- **Deduplication**: Does anything repeat what a parent AGENTS.md already says? If so, remove it and rely on the hierarchy.
- **Specificity**: Replace vague statements with concrete ones. Not "be careful with auth" but "place logic after the `require_*` call".
- **Target length**: 50-150 lines for new files. If longer, compress or split into child nodes.

## Important guidelines

- Be conservative — only flag things that are genuinely wrong or missing. AGENTS.md files are intentionally concise and don't need to document every file.
- Don't suggest adding content that's obvious from the code itself. AGENTS.md captures non-obvious patterns, gotchas, and high-level structure. Equally, flag *existing* content that merely restates the code — full function signatures, trivial examples, and file enumerations are low-signal and should be trimmed or replaced with the hidden knowledge around them.
- Don't trust that existing AGENTS.md content was ever correct. Verify factual claims (behaviors, signatures, responsibility attribution) against the source code, not just against the diff. Content can be wrong from day one.
- Don't suggest stylistic rewrites. Focus on factual accuracy and signal density.
- When in doubt about whether something is stale, check the filesystem to confirm rather than guessing from the diff alone.
- Respect the existing level of detail in each AGENTS.md. If a file only lists top-level directories, don't suggest adding individual files.
- Look for undocumented invariants — parallel implementations that must stay in sync, ordering constraints, singleton behaviors, cleanup responsibilities. These are the highest-value additions because they're invisible in code and cause the most breakage when violated.
