# Agentic Framework Design: Intent Layer for Prefect

## Executive Summary

This document designs a comprehensive Intent Layer system for the Prefect codebase, based on the principles from [Intent Systems](https://intent-systems.com/blog/intent-layer). The Intent Layer is a hierarchical context system embedded in the repository as `AGENTS.md` files placed at semantic boundaries. It gives AI agents the "mental model" that experienced engineers carry — understanding of boundaries, invariants, hidden contracts, and architectural decisions — so agents spend tokens implementing rather than exploring.

We already have 16 intent nodes covering ~1,253 lines of guidance. This framework defines how to grow that to ~80+ nodes covering the full codebase, maintain them automatically via GitHub Agentic workflows, and incrementally migrate without disrupting current development.

---

## 1. Current State Assessment

### What We Have

| Area | Nodes | Lines | Coverage |
|------|-------|-------|----------|
| Root | 1 | 108 | Project overview, conventions, logging |
| docs/ | 1 | 104 | Mintlify structure, frontmatter |
| src/prefect/ | 2 | 109 | Core SDK overview, settings (detailed) |
| src/prefect/server/ | 1 | 25 | Server overview (thin) |
| src/integrations/ | 1 | 25 | Integration overview (thin) |
| tests/ | 1 | 35 | Testing guidelines (thin) |
| ui-v2/ | 9 | 847 | React migration, components, e2e, API, routes, etc. |
| **Total** | **16** | **1,253** | |

### Key Gaps

**Backend (src/prefect/)**: 24 of 26 subdirectories have zero guidance. Critical modules like `client/`, `cli/`, `workers/`, `runner/`, `events/`, `deployments/`, `concurrency/`, `blocks/`, and `logging/` are completely undocumented for agents.

**Server (src/prefect/server/)**: 10 subdirectories with zero guidance. The API layer, database/ORM models, orchestration policies, and background services — the most architecturally complex parts of the codebase — have no intent nodes.

**Integrations (src/integrations/)**: 18 integration packages (AWS, GCP, Azure, Kubernetes, Dask, Ray, dbt, etc.) have no individual guidance.

**Tests (tests/)**: 30 test subdirectories covered only by a 35-line root node with no per-module testing patterns.

### What's Working

The UI v2 section demonstrates what good coverage looks like: 9 nodes totaling 847 lines with clear component patterns, E2E testing guidance, API query conventions, and Storybook setup. The `settings/` node (82 lines) shows how a single well-written node can encode complex patterns (backward compatibility, testing, `PREFECT_` env var mapping). The root node captures cross-cutting concerns (logging hierarchy, code conventions, PR style) at the correct level per the Least Common Ancestor principle.

---

## 2. Design Principles

These principles govern all Intent Layer work.

### 2.1 Fractal Compression

Each node summarizes its subtree. Parent nodes summarize child intent nodes, not raw code. An agent reading `src/prefect/AGENTS.md` gets the shape of the entire SDK; drilling into `src/prefect/client/AGENTS.md` reveals client-specific contracts. This creates a "zoom" effect: broad context at the top, specific detail where the agent is working.

### 2.2 Least Common Ancestor (LCA)

A fact lives at the shallowest node where it's relevant. Cross-cutting conventions (Python version, import style, logging) belong at the root. Server-specific database patterns belong at `server/`. API endpoint conventions belong at `server/api/`. Never duplicate upward or downward.

**Current violation to fix**: The root AGENTS.md contains detailed logging guidance that's specific to `src/prefect/logging/` and `src/prefect/engine.py`. This should be refactored — a summary stays at root, detail moves to leaf nodes.

### 2.3 Semantic Boundaries

Intent nodes align with architectural boundaries, not arbitrary directory structure. A node exists where:
- Responsibility changes (client vs. server)
- Technology changes (Python vs. TypeScript, SQLAlchemy vs. Pydantic)
- Team ownership changes
- Conventions diverge from the parent

Not every directory needs a node. A directory that simply contains more of the same thing as its parent (e.g., `tests/test_flows.py`) inherits the parent node.

### 2.4 Negative Space

What NOT to do is as valuable as what to do. Every node should include anti-patterns where they exist. Example: "Do NOT import server modules from client code" or "Do NOT use `logging.getLogger()` — use `get_logger()` from `prefect.logging`."

### 2.5 Token Budget

Each leaf node targets 1,000–3,000 tokens (~40–120 lines of markdown). Parent/summary nodes can be smaller. The combined ancestor chain for any working directory should stay under 8,000 tokens. This ensures agents have room for actual code in their context window.

---

## 3. Target Node Architecture

### 3.1 Hierarchy Map

Below is the target hierarchy. Nodes marked ● exist today. Nodes marked ○ are new. Indentation shows parent-child relationships.

```
● /                              Root: project overview, conventions, tech stack
├── ● docs/                      Documentation: Mintlify, frontmatter, navigation
├── ● src/prefect/               Core SDK: flows, tasks, states, blocks, deployments
│   ├── ○ client/                Client SDK: HTTP client, schemas, type contracts
│   │   ├── ○ orchestration/     Orchestration client: server API methods
│   │   └── ○ schemas/           Client schemas: request/response models
│   ├── ○ cli/                   CLI: Typer app, command groups, output formatting
│   ├── ○ concurrency/           Concurrency: v1 sync primitives, rate limiting
│   ├── ○ deployments/           Deployments: recipes, steps, templates, schedules
│   ├── ○ events/                Events: emission, filtering, schemas, triggers
│   ├── ○ blocks/                Blocks: typed storage, infrastructure, notifications
│   ├── ○ logging/               Logging: hierarchy, handlers, API log pipeline
│   ├── ○ runner/                Runner: flow execution, subprocess management
│   ├── ○ workers/               Workers: base class, work pools, polling loop
│   ├── ○ runtime/               Runtime: context variables, flow/task/deployment info
│   ├── ○ locking/               Locking: distributed lock interface, backends
│   ├── ○ utilities/             Utilities: shared helpers, schema tools
│   ├── ○ types/                 Types: core type definitions, internal protocols
│   ├── ○ _internal/             Internal: compatibility, concurrency, pydantic utils
│   ├── ● settings/              Settings: PREFECT_ env vars, profiles, defaults
│   └── ● server/                Server: API, database, orchestration, services
│       ├── ○ api/               API: FastAPI routes, dependencies, middleware
│       ├── ○ database/          Database: async engine, migrations, connection mgmt
│       ├── ○ models/            Models: SQLAlchemy ORM, CRUD operations
│       ├── ○ schemas/           Schemas: Pydantic request/response validation
│       ├── ○ orchestration/     Orchestration: state transitions, policies, rules
│       ├── ○ events/            Server events: triggers, actions, reactive automation
│       ├── ○ services/          Services: background workers, scheduling, cleanup
│       └── ○ utilities/         Server utilities: shared server helpers
├── ○ src/integrations/          Integration packages (already exists, needs expansion)
│   ├── ○ prefect-aws/           AWS: S3, ECS, Lambda, credentials
│   ├── ○ prefect-gcp/           GCP: Cloud Run, GCS, BigQuery, credentials
│   ├── ○ prefect-azure/         Azure: ACI, Blob Storage, credentials
│   ├── ○ prefect-kubernetes/    Kubernetes: jobs, workers, manifests
│   ├── ○ prefect-docker/        Docker: containers, images, registries
│   ├── ○ prefect-dbt/           dbt: CLI, Cloud, artifact parsing
│   ├── ○ prefect-redis/         Redis: result storage, lock backend, lease
│   ├── ○ prefect-sqlalchemy/    SQLAlchemy: database blocks, credentials
│   └── ○ (others as needed)     Remaining integrations follow same pattern
├── ● tests/                     Testing: conventions, fixtures, mocking
│   ├── ○ server/                Server tests: database fixtures, API test patterns
│   └── ○ client/                Client tests: mock server, response fixtures
└── ● ui-v2/                     UI v2: React, Tailwind, TanStack (well-covered)
    ├── ● e2e/                   E2E tests: Playwright patterns
    ├── ● src/api/               API layer: query factories, mutations
    ├── ● src/components/        Components: forms, icons, patterns
    ├── ● src/hooks/             Hooks: custom hook guidelines
    ├── ● src/mocks/             Mocks: factory patterns
    ├── ● src/routes/            Routes: TanStack Router
    ├── ● src/storybook/         Storybook: stories, decorators
    └── ● src/utils/             Utils: utility functions
```

**Total target: ~50 nodes** (16 existing + ~34 new). This is deliberately conservative — we add nodes only at true semantic boundaries, not every directory.

### 3.2 Priority Tiers

**Tier 1 — High-impact, high-traffic areas (implement first)**:
1. `src/prefect/client/` — Agents constantly touch client code
2. `src/prefect/server/api/` — Most common change target
3. `src/prefect/server/models/` — ORM patterns are non-obvious
4. `src/prefect/server/orchestration/` — State machine rules are the hardest to get right
5. `src/prefect/workers/` — Complex base class with polling, cancellation, lifecycle
6. `src/prefect/events/` — Event system has subtle contracts
7. `src/prefect/deployments/` — Deployment creation flow is multi-step

**Tier 2 — Important supporting modules**:
8. `src/prefect/cli/` — Command structure, output conventions
9. `src/prefect/runner/` — Flow execution lifecycle
10. `src/prefect/blocks/` — Block type system, serialization
11. `src/prefect/logging/` — Move detailed logging guidance from root
12. `src/prefect/server/database/` — Connection management, migration patterns
13. `src/prefect/server/services/` — Background service lifecycle
14. `src/prefect/server/schemas/` — Schema conventions, validation patterns

**Tier 3 — Supporting infrastructure and integrations**:
15. `src/prefect/concurrency/` — Rate limiting patterns
16. `src/prefect/runtime/` — Context variable contracts
17. `src/prefect/locking/` — Lock interface contracts
18. `src/prefect/settings/` — Already exists, enhance
19. `src/integrations/prefect-kubernetes/` — Most-used integration
20. `src/integrations/prefect-aws/` — Second most-used
21. `tests/server/` — Server test patterns
22. Remaining integrations

**Tier 4 — Internal and utilities**:
23. `src/prefect/_internal/` — Internal utilities
24. `src/prefect/utilities/` — Shared helpers
25. `src/prefect/types/` — Type definitions
26. `tests/client/` — Client test patterns

---

## 4. Node Content Standard

Every intent node follows this template. Not every section is required — use only what adds value for the specific directory.

```markdown
# {Directory Name}

{One-sentence purpose statement.}

## Scope

- Responsible for: {what this module owns}
- NOT responsible for: {explicit exclusions — what belongs elsewhere}

## Key Concepts

{2-5 bullet points explaining the mental model an agent needs.}

## Entry Points & Contracts

{Public APIs, expected inputs/outputs, invariants that must hold.}

## Patterns

{Canonical examples of how to do things correctly in this module.}

## Anti-Patterns

{Things that look reasonable but are wrong. Include WHY they're wrong.}

## Dependencies

- Depends on: {upstream modules this code imports from}
- Depended on by: {downstream modules that import from here}
- Related docs: {links to relevant documentation}

## Testing

{How to test changes in this module. Specific fixtures, patterns, gotchas.}
```

### Content Rules

1. **Dense prose, not filler.** Every sentence should teach something an agent wouldn't know from reading the code alone.
2. **Tacit knowledge first.** Prioritize "hidden" knowledge: why decisions were made, what breaks if invariants are violated, what the code doesn't tell you.
3. **No code dumps.** Short inline snippets (1-5 lines) are fine for patterns. Don't paste entire functions.
4. **Use downlinks.** Point to child AGENTS.md files and external docs rather than inlining their content.
5. **Version-stamp volatile facts.** If guidance depends on a specific version or state of the code, mark it: `<!-- as of 2026-02 -->`.

---

## 5. Automated Maintenance via GitHub Agentic Workflows

The Intent Layer must stay synchronized with the codebase. Stale guidance is worse than no guidance — it creates confident, wrong agents. This section defines the automation that keeps nodes current.

### 5.1 Intent Drift Detection (New Workflow)

**Trigger**: Every PR merged to `main`.

**Purpose**: Detect when code changes may have invalidated intent nodes.

```yaml
# .github/workflows/intent-drift-detection.yaml
name: Intent Drift Detection

on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  detect-drift:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Identify changed files
        id: changes
        run: |
          # Get all files changed in the merged PR
          CHANGED=$(git diff --name-only ${{ github.event.pull_request.base.sha }} \
                                          ${{ github.event.pull_request.merge_commit_sha }})
          echo "changed_files<<EOF" >> $GITHUB_OUTPUT
          echo "$CHANGED" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Map changes to intent nodes
        id: affected
        run: |
          # For each changed file, walk up to find the nearest AGENTS.md
          # If the AGENTS.md was NOT also modified in this PR, flag it
          python scripts/intent-layer/detect_drift.py \
            --changed-files "${{ steps.changes.outputs.changed_files }}" \
            --output affected_nodes.json

      - name: Report drift candidates
        if: steps.affected.outputs.has_drift == 'true'
        run: |
          # Post a comment on the merged PR noting which intent nodes
          # may need updating
          gh pr comment ${{ github.event.pull_request.number }} \
            --body "$(python scripts/intent-layer/format_drift_report.py affected_nodes.json)"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Drift detection logic** (`scripts/intent-layer/detect_drift.py`):

1. For each changed file, find the nearest ancestor AGENTS.md
2. Classify the change: new file, deleted file, modified public API, modified internal
3. If the change is "structural" (new/deleted files, changed function signatures, new exports) AND the governing AGENTS.md was not also updated in the PR, flag it
4. Simple heuristics: changes to `__init__.py` exports, new class definitions, renamed functions, new CLI commands → likely need intent node update
5. Changes to function bodies, test files, docstrings → usually don't need intent node update

### 5.2 Intent Node Auto-Update (Claude-Powered)

**Trigger**: When drift detection flags affected nodes, OR on a weekly schedule.

**Purpose**: Use the existing Claude Code GitHub Action to propose intent node updates.

```yaml
# .github/workflows/intent-node-update.yaml
name: Intent Node Auto-Update

on:
  workflow_dispatch:
    inputs:
      target_node:
        description: 'Path to specific AGENTS.md to update (or "all-drifted")'
        required: true
  schedule:
    # Weekly sweep: every Monday at 6 AM UTC
    - cron: '0 6 * * 1'

jobs:
  update-nodes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Identify nodes to update
        id: targets
        run: |
          if [ "${{ github.event.inputs.target_node }}" = "all-drifted" ]; then
            python scripts/intent-layer/find_drifted_nodes.py --since "1 week ago"
          else
            echo "${{ github.event.inputs.target_node }}"
          fi

      - name: Create update branch
        run: |
          git checkout -b intent-layer/auto-update-$(date +%Y%m%d)

      - name: Generate updates via Claude
        uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            You are updating AGENTS.md intent nodes for the Prefect codebase.

            Target nodes: ${{ steps.targets.outputs.nodes }}

            For each target node:
            1. Read the current AGENTS.md content
            2. Read the source code in that directory and its immediate children
            3. Compare: does the AGENTS.md accurately describe what the code does?
            4. If not, update the AGENTS.md to reflect the current state
            5. Follow the content standard (see docs/agentic-framework-design.md §4)

            Rules:
            - Preserve existing guidance that is still accurate
            - Add new guidance for new code/patterns
            - Remove guidance for deleted code
            - Keep nodes under 120 lines / 3000 tokens
            - Do NOT change code, only AGENTS.md files

      - name: Create PR
        run: |
          git add "*/AGENTS.md"
          git commit -m "chore: auto-update intent nodes"
          git push -u origin HEAD
          gh pr create \
            --title "chore: weekly intent node sync" \
            --body "Automated update of AGENTS.md files to reflect recent code changes." \
            --label "documentation"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 5.3 Intent Node Validation (CI Check)

**Trigger**: Every PR that modifies an AGENTS.md file.

**Purpose**: Ensure intent nodes meet quality standards.

```yaml
# .github/workflows/intent-node-validation.yaml
name: Intent Node Validation

on:
  pull_request:
    paths:
      - '**/AGENTS.md'
      - '**/CLAUDE.md'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Validate intent nodes
        run: python scripts/intent-layer/validate_nodes.py
```

**Validation rules** (`scripts/intent-layer/validate_nodes.py`):

1. **Symlink check**: Every AGENTS.md has a corresponding CLAUDE.md symlink (and vice versa)
2. **Token budget**: No single node exceeds 4,000 tokens; warn above 3,000
3. **Ancestor chain budget**: No working directory's full ancestor chain exceeds 10,000 tokens
4. **Structure check**: Each node starts with a heading and purpose statement
5. **Orphan check**: No AGENTS.md exists in a directory with zero source files (excluding the root)
6. **Staleness heuristic**: Warn if the AGENTS.md hasn't been updated in 90 days but the directory's source files have changed significantly

### 5.4 Agent Feedback Loop

When AI agents (Claude Code, Devin, or others) work in the codebase and encounter missing context, they should be able to surface it. This creates a reinforcement loop where agent struggles become intent layer improvements.

**Mechanism**: Extend the existing `claude.yml` workflow's prompt to include:

```
If you encounter areas where AGENTS.md guidance is missing, incomplete,
or contradicts the actual code, note this at the end of your response
under a "## Intent Layer Gaps" heading. Include:
- Which directory lacked guidance
- What knowledge you had to discover by reading code
- What should be added to the nearest AGENTS.md
```

These gaps are collected by a scheduled workflow that:
1. Searches recent Claude Code PR comments for "## Intent Layer Gaps"
2. Aggregates them into a tracking issue
3. Prioritizes by frequency (if multiple agents hit the same gap, it's urgent)

---

## 6. Incremental Migration Plan

Moving from 16 nodes to 50+ nodes is a multi-phase effort. Each phase is independently valuable — there is no "big bang" cutover.

### Phase 0: Foundation (Week 1)

**Goal**: Establish tooling and standards before writing any new nodes.

Tasks:
1. Create `scripts/intent-layer/` directory with the validation, drift detection, and formatting scripts described in §5
2. Add the Intent Node Validation workflow (§5.3) — this enforces quality from day one
3. Add CLAUDE.md symlinks for any AGENTS.md files that lack them (and vice versa)
4. Refactor the root AGENTS.md: move the detailed logging guidance (lines about `APILogHandler`, `flow_run_logger()`, worker logging) into a new `src/prefect/logging/AGENTS.md` node, leaving a summary + downlink at root
5. Audit and tighten existing nodes against the content standard (§4)

**Validation**: All existing nodes pass the new validation workflow.

### Phase 1: Tier 1 Nodes (Weeks 2-3)

**Goal**: Cover the highest-traffic, highest-complexity areas.

Write 7 new intent nodes (Tier 1 from §3.2):
- `src/prefect/client/AGENTS.md`
- `src/prefect/server/api/AGENTS.md`
- `src/prefect/server/models/AGENTS.md`
- `src/prefect/server/orchestration/AGENTS.md`
- `src/prefect/workers/AGENTS.md`
- `src/prefect/events/AGENTS.md`
- `src/prefect/deployments/AGENTS.md`

**Process for each node**:
1. Subject matter expert (or experienced contributor) reads the code and identifies: purpose, scope, key contracts, patterns, anti-patterns, testing approach
2. Draft the node following the template (§4)
3. Have a second person review for accuracy and completeness
4. Submit as a PR; the validation workflow (§5.3) runs automatically
5. Create the CLAUDE.md symlink alongside each new AGENTS.md

**Validation**: An agent given a task in each Tier 1 area should be able to complete it with fewer exploration steps than before. Measure by comparing context token usage before/after on representative tasks.

### Phase 2: Tier 2 Nodes + Drift Detection (Weeks 4-5)

**Goal**: Cover supporting modules and activate automated maintenance.

Tasks:
1. Write 7 Tier 2 intent nodes (§3.2 items 8-14)
2. Deploy the Intent Drift Detection workflow (§5.1)
3. Deploy the Agent Feedback Loop (§5.4)
4. Add the drift detection script and integrate it into the merge process
5. Begin collecting feedback from Claude Code and Devin interactions

**Validation**: Drift detection correctly flags PRs that modify code covered by intent nodes. No false positives on pure-refactor PRs that don't change semantics.

### Phase 3: Tier 3 Nodes + Auto-Update (Weeks 6-8)

**Goal**: Cover integrations and activate automated node updates.

Tasks:
1. Write Tier 3 intent nodes — prioritize the top integrations (Kubernetes, AWS, GCP, Azure, Redis, dbt) based on usage/contribution frequency
2. Deploy the Intent Node Auto-Update workflow (§5.2)
3. Run the first automated sweep and review results
4. Tune drift detection heuristics based on Phase 2 feedback

**Validation**: The auto-update workflow proposes reasonable changes that require minimal human editing. Human reviewers accept >80% of suggestions with minor modifications.

### Phase 4: Tier 4 + Steady State (Weeks 9-10)

**Goal**: Fill remaining gaps and establish ongoing maintenance rhythm.

Tasks:
1. Write remaining Tier 4 nodes (internal utilities, test patterns)
2. Establish the weekly auto-update cadence
3. Create a quarterly "Intent Layer Health" review process
4. Document the Intent Layer contribution process for new team members

**Validation**: Full codebase coverage at semantic boundaries. All agent-facing directories have either a direct node or inherit from a meaningful parent. Agent feedback loop shows decreasing gap reports over time.

---

## 7. Measuring Success

### 7.1 Quantitative Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Intent node count | 16 | 50+ |
| Lines of guidance | 1,253 | 4,000-5,000 |
| Backend coverage (nodes / semantic boundaries) | 6% | 80%+ |
| Agent context tokens used for exploration (per task) | Unmeasured | Decrease by 40%+ |
| Agent task completion rate (first attempt) | Unmeasured | Increase measurably |
| Intent node staleness (nodes >90 days without update in active code areas) | Unknown | <10% |

### 7.2 Qualitative Indicators

- Agents stop asking "which module handles X?" — intent nodes provide the map
- PR reviews from agents require fewer rounds of revision for architectural alignment
- New team members report faster onboarding (intent nodes serve humans too)
- The agent feedback loop produces fewer gap reports over time (convergence)

### 7.3 Anti-Metrics (Things to Watch For)

- **Bloat**: Nodes growing past 4,000 tokens — signals they need splitting
- **Staleness**: Drift detection firing constantly — signals the update cadence is too slow or the codebase is changing faster than maintenance can keep up
- **False confidence**: Agents citing intent nodes that are outdated — worse than no guidance at all
- **Duplication**: Same guidance appearing in multiple nodes — violates LCA principle

---

## 8. Integration with Existing Agentic Workflows

### 8.1 Claude Code Action (`claude.yml`)

The existing Claude Code GitHub Action already loads AGENTS.md files automatically (this is a built-in feature of Claude Code). Improvements:

1. **Enhanced system prompt**: Add to the Claude Code action's prompt:
   - Instruction to read the nearest AGENTS.md before making changes
   - Instruction to report intent layer gaps (§5.4)
   - Instruction to update AGENTS.md when making structural changes

2. **Expanded permissions**: Currently restricted to `uv:*` and `gh:*` bash commands. No changes needed — AGENTS.md files are read automatically.

### 8.2 Devin Flaky Test Fixer (`devin-fix-flaky-tests.yaml`)

Devin's playbook should reference the intent layer:

1. Update the Devin playbook to include: "Read the AGENTS.md in the test directory and the source directory being tested before investigating the flaky test."
2. This ensures Devin understands test patterns and module contracts before proposing fixes.

### 8.3 Pre-Commit Hooks

Add a lightweight pre-commit hook that warns (does not block) when:
- A new directory is created under `src/` without an AGENTS.md
- An AGENTS.md is modified but its CLAUDE.md symlink is broken

This is advisory, not blocking, to avoid disrupting development flow.

### 8.4 Future: Agentic PR Review

As the intent layer matures, enable a new workflow:

```yaml
# Future: .github/workflows/intent-aware-review.yaml
name: Intent-Aware PR Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Review this PR for consistency with the AGENTS.md guidance
            in the affected directories. Check:
            1. Do changes follow documented patterns?
            2. Do changes violate documented anti-patterns?
            3. Are contracts/invariants preserved?
            4. Should AGENTS.md be updated to reflect these changes?
```

This creates a closed loop: intent nodes guide development, and PRs are reviewed against them.

---

## 9. Node Generation Process

### 9.1 Human-Led (Preferred for Tier 1)

For the most critical modules, an experienced engineer should write the first draft:

1. **Interview**: Spend 15-30 minutes with the module owner. Ask:
   - "What does an agent need to know before touching this code?"
   - "What's the most common mistake someone new makes here?"
   - "What invariants must never be violated?"
   - "What patterns should be followed? What's the canonical way to add a new X?"

2. **Draft**: Write the AGENTS.md following the template (§4). Target 60-100 lines.

3. **Validate**: Have the engineer review for accuracy. Run the validation script.

4. **Test**: Give an agent a representative task in that module and observe whether the intent node helps.

### 9.2 Agent-Assisted (Suitable for Tier 2-4)

For lower-priority modules, use Claude Code to generate initial drafts:

1. **Prompt Claude Code** in the target directory:
   ```
   Read all source files in this directory and its immediate children.
   Based on the code, write an AGENTS.md following the template in
   docs/agentic-framework-design.md §4. Focus on:
   - What this module does (purpose, scope)
   - Public API contracts and invariants
   - Patterns and anti-patterns you observe
   - Testing approach
   Keep it under 100 lines. Be dense — every sentence should teach
   something not obvious from the code.
   ```

2. **Human review**: An engineer reviews the draft for accuracy. Agent-generated nodes are likely ~70% accurate — the review catches hallucinated contracts and missing tacit knowledge.

3. **Iterate**: The engineer fills in what the agent missed. This is faster than writing from scratch because the structure and obvious content are already in place.

### 9.3 Bootstrapping Script

Create a script that generates skeleton AGENTS.md files for directories that lack them:

```python
# scripts/intent-layer/bootstrap_node.py
# For a given directory:
# 1. List all .py files and their top-level definitions (classes, functions)
# 2. Read __init__.py exports
# 3. Find the nearest ancestor AGENTS.md and read it for context
# 4. Generate a skeleton with sections pre-filled from static analysis
# 5. Mark sections with TODO comments for human review
```

This reduces the activation energy for creating new nodes.

---

## 10. Governance

### 10.1 Ownership

Intent nodes are owned by the same teams/individuals who own the code they describe, per `CODEOWNERS`. When CODEOWNERS changes, the intent node reviewer changes too.

Add to `.github/CODEOWNERS`:
```
# Intent Layer - mirrors code ownership
src/prefect/**/AGENTS.md    @cicdw @desertaxle @zzstoatzz @chrisguidry
src/integrations/**/AGENTS.md  @cicdw @desertaxle @zzstoatzz @chrisguidry
ui-v2/**/AGENTS.md          @aaazzam @desertaxle @devinvillarosa
```

### 10.2 Review Process

- **Human-written nodes**: Standard PR review by code owners
- **Agent-generated updates**: Weekly batch review. A designated reviewer (rotating) checks the auto-update PR each Monday.
- **Drift reports**: Addressed within the sprint where they're filed, or explicitly deferred with a comment explaining why.

### 10.3 Deprecation

When a module is deprecated or removed:
1. Delete the AGENTS.md and CLAUDE.md symlink
2. If the parent AGENTS.md references the removed child, update the parent
3. The drift detection workflow will catch any dangling references

---

## 11. Appendix: Example Intent Nodes

### Example A: `src/prefect/server/orchestration/AGENTS.md`

```markdown
# Orchestration

State transition engine for flow runs and task runs. This is the most
safety-critical module in the server — incorrect orchestration rules
can leave runs stuck or in impossible states.

## Scope

- Responsible for: state transition validation, orchestration rules/policies,
  run lifecycle management (pending → running → completed/failed/cancelled)
- NOT responsible for: API routing (see ../api/), database queries (see ../models/),
  event emission (see ../events/)

## Key Concepts

- **Orchestration rules** are composable policies that approve/reject/modify
  state transitions. They run in sequence; any rule can reject a transition.
- **State types** form a DAG: PENDING → RUNNING → COMPLETED|FAILED|CANCELLED|CRASHED.
  PAUSED can transition to RUNNING or CANCELLED. CANCELLING → CANCELLED.
- The **proposed state** is what the client wants. The **validated state** is what
  the orchestration engine allows after applying all rules.
- Rules have access to the full `OrchestrationContext` including the current state,
  proposed state, run object, and database session.

## Anti-Patterns

- Do NOT bypass orchestration by writing state directly to the database.
  All state changes must go through the orchestration engine.
- Do NOT assume the validated state equals the proposed state. Rules can
  modify the proposed state (e.g., converting COMPLETED to FAILED if
  result storage fails).
- Do NOT add rules that depend on ordering. Rules should be independently
  correct.

## Testing

Test orchestration rules with `OrchestrationContext` fixtures. Each rule
should be tested for: allowed transitions, rejected transitions, and
edge cases (re-entrant transitions, terminal states).
```

### Example B: `src/prefect/client/AGENTS.md`

```markdown
# Client SDK

HTTP client for communicating with the Prefect server/cloud API.
This is the boundary between SDK code and the server — all server
communication flows through this module.

## Scope

- Responsible for: HTTP request/response handling, authentication,
  API method wrappers, client-side schemas, retry logic
- NOT responsible for: server-side logic, CLI commands (see ../cli/),
  flow/task execution (see ../runner/, ../workers/)

## Key Concepts

- `PrefectClient` is the async client. `SyncPrefectClient` wraps it
  for synchronous use. Most SDK code should use the async client.
- Client methods map 1:1 to API endpoints. Method names follow
  `{verb}_{resource}` convention: `read_flow_run`, `create_deployment`.
- `schemas/` contains Pydantic models for API request/response bodies.
  These are CLIENT-SIDE schemas — they may differ from server schemas.
- `types/` contains type definitions used across client code.

## Anti-Patterns

- Do NOT import from `prefect.server` in client code. The client
  package is published separately as `prefect-client` and must not
  depend on server internals.
- Do NOT add business logic to client methods. They should be thin
  wrappers around HTTP calls.

## Dependencies

- Depends on: httpx, pydantic, prefect.settings
- Depended on by: virtually everything — flows, tasks, CLI, workers, runner
- Note: changes to client schemas may require parallel changes in
  `client/pyproject.toml` (see root AGENTS.md)
```

---

## 12. Summary

The Intent Layer transforms how AI agents interact with the Prefect codebase. Instead of exploring in the dark, agents start with a hierarchical map of purpose, contracts, patterns, and pitfalls. The key principles are:

1. **Hierarchical compression**: Broad context at the root, specific detail at the leaves
2. **Semantic boundaries**: Nodes align with architectural boundaries, not arbitrary directories
3. **Least Common Ancestor**: Facts live at the shallowest relevant level, never duplicated
4. **Automated maintenance**: Drift detection, auto-updates, and feedback loops keep nodes current
5. **Incremental adoption**: Each phase is independently valuable; no big-bang migration

The framework leverages existing infrastructure — Claude Code Action, Devin, pre-commit hooks, CODEOWNERS — rather than building from scratch. The 50-node target provides comprehensive coverage while staying maintainable. The automation ensures the Intent Layer improves over time rather than decaying.
