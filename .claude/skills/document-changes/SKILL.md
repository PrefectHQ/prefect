---
name: document-changes
description: Analyze source code changes on the current branch and identify documentation that is stale, inaccurate, or missing. Use before creating a PR to check if docs need updating, or in CI after merges to main to automatically fix docs. Trigger when the user mentions "doc changes", "docs update", "check docs", "document changes", or wants to know if code changes affect documentation.
---

# Document Changes

Analyze source code changes to find documentation that is stale, inaccurate, or missing, then either report findings or directly apply fixes.

## Modes

- **Report mode (default, local dev):** Produce a structured report of findings with suggested fixes. Offer to apply them.
- **Edit mode (CI):** Directly apply fixes to existing doc pages. Do not create entirely new pages — flag those as recommendations in the PR body instead.

The mode is determined by how the skill is invoked. Local interactive use defaults to report mode. CI sets edit mode via the prompt.

## Prerequisites

Before making any doc edits, read the write-docs skill at `.claude/skills/write-docs/SKILL.md`. All edits must follow its conventions for tone, components, frontmatter, code blocks, and testing directives.

## Workflow

### 1. Determine the diff

Figure out what changed relative to the base branch:

- **On a feature branch (pre-PR):** diff against main
  ```bash
  git diff main...HEAD --name-status
  git diff main...HEAD -- 'src/prefect/' 'src/integrations/'
  ```
- **After a merge to main (CI):** read the diff provided at `/tmp/diff.patch`
- **Explicit check:** diff against main

Filter the diff to only source code changes. Skip:
- Test files (`**/tests/**`)
- CI/workflow files (`.github/`)
- Documentation files (`docs/`, `*.md`, `*.mdx`)
- Lock files (`uv.lock`, `package-lock.json`)
- UI files (`ui-v2/`)

### 2. Extract public API surface changes

Scan the diff for changes that users would encounter:

**Function and class signatures:**
- New, renamed, or removed public functions/classes/methods
- Changed parameters (added, removed, renamed, retyped)
- Changed default values
- Changed return types

**CLI commands:**
- New, renamed, or removed commands (look for `@app.command()`, click/typer decorators)
- Changed arguments or options
- Changed help text

**Configuration and settings:**
- New, renamed, or removed settings (look for `Setting`, `Field` in settings classes)
- Changed defaults or validation
- Changed environment variable names

**Behavioral changes:**
- Changed error types or messages users would see
- Changed lifecycle behavior (e.g., retry logic, state transitions)
- Changed defaults that affect runtime behavior

**Skip:**
- Private/internal symbols (names starting with `_` in `_internal` modules)
- Type-only changes that don't affect runtime behavior
- Import reorganizations that don't change the public API
- Pure refactors with no behavioral change

### 3. Map changes to existing docs

For each extracted change, search the docs for references. Use parallel searches for efficiency.

**Search strategy:**
- Grep `docs/` for function names, class names, CLI command names, setting names
- Check concept pages that explain the changed feature's behavior
- Check how-to guides that demonstrate the changed API
- Check get-started pages if fundamental APIs changed
- Check integration docs if integration entry points changed

**Build a findings list with these categories:**

**Stale — docs describe something that changed:**
- Wrong default value documented
- Old parameter name or signature
- Removed feature still documented
- Behavior description that no longer matches the code
- Code examples using old API

**Missing — new public API/feature with no doc coverage:**
- New public function/class with no mention in any doc page
- New CLI command not documented
- New setting not listed in configuration docs
- New feature that extends an existing documented concept

**Broken examples — code blocks that reference changed APIs:**
- Code blocks using removed or renamed functions
- Code blocks with old parameter names
- Code blocks that would produce different output than described

### 4. Produce output

#### Report mode (local dev)

Print a structured report grouped by doc file:

```markdown
## Documentation Changes Report

### `docs/v3/concepts/flows.mdx`

1. **[Stale]** Line 45: `@flow(retries=3)` — `retries` parameter renamed to `max_retries` in src/prefect/flows.py
   - **Suggested fix:** Update parameter name in code example and surrounding prose

2. **[Broken example]** Line 78-85: Code block uses `flow.run()` which was removed
   - **Suggested fix:** Replace with `flow()` direct invocation

### `docs/v3/how-to-guides/workflows/retries.mdx`

1. **[Stale]** Line 23: "Default retry delay is 5 seconds" — default changed to 10 seconds in this branch
   - **Suggested fix:** Update to "Default retry delay is 10 seconds"

### Missing coverage

1. **[Missing]** New `@flow(on_cancellation=...)` hook added — no docs mention this parameter
   - **Recommendation:** Add a section to `docs/v3/concepts/flows.mdx` under "Flow lifecycle hooks" or create a new how-to guide

### No changes needed
- `docs/v3/get-started/quickstart.mdx` — references checked, all current
```

After presenting the report, offer:
- **Apply fixes** — make the suggested edits to existing pages (follow write-docs skill conventions)
- **Skip** — if the user disagrees with findings or wants to handle manually

#### Edit mode (CI)

Directly apply fixes for **Stale** and **Broken example** findings on existing pages:
- Read each affected doc file
- Make targeted, minimal edits to fix the specific issues
- Do not rewrite surrounding content
- Do not change tone, style, or structure beyond what's needed
- For code blocks, ensure the fix is syntactically valid
- Add `{/* pmd-metadata: notest */}` only if the fixed code genuinely can't be tested

For **Missing** coverage findings, do not create new pages. Instead, collect them for the PR body.

### 5. Quality gate (edit mode only)

Before considering edits complete, verify each change:
- Follows write-docs tone (second person, active voice, no marketing language)
- Uses Mintlify components correctly (not markdown admonitions)
- Preserves existing frontmatter (title, description, keywords)
- Does not add or remove pages from `docs/docs.json`
- Code blocks are syntactically valid Python/bash
- Changes are minimal — only what's needed to fix the finding

### 6. Offer next steps (report mode only)

After applying fixes (if the user chose to), mention:
- Run `just lint` in `docs/` to check Vale style
- Run markdown tests if code blocks were modified
- Any missing coverage items that need new content written (suggest using the write-docs skill)

## Important guidelines

- **Be conservative.** Only flag things that are genuinely wrong or missing. A doc page that doesn't mention every parameter is fine — it's stale only if it mentions the *wrong* value or a *removed* thing.
- **Don't rewrite for style.** If the prose is accurate, leave it alone even if you'd write it differently.
- **Verify before flagging.** Read both the diff and the current doc file. A grep hit doesn't mean the doc is wrong — read the context.
- **Respect doc scope.** Not every public API needs docs. Flag missing coverage for features users would reasonably expect to find documented, not for every internal helper that happens to be public.
- **Minimize blast radius in CI.** Small, targeted fixes only. If a finding requires judgment about page structure or new content, leave it as a recommendation rather than an automated edit.
- **Don't touch auto-generated pages.** Skip `v3/examples/`, `v3/api-ref/`, and any file noted as auto-generated.
- **Check code block test directives.** If you modify a code block, check whether it has `pmd-metadata` directives and preserve them. If you're unsure whether a modified block is testable, mark it `notest` and note why.
