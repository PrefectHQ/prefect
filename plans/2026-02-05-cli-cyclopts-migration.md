# Prefect CLI: Cyclopts Migration Plan

## Goal

Migrate the Prefect CLI from Typer to Cyclopts in an incremental, low-risk way that preserves CLI behavior and improves help/discovery startup time. The plan must define command registration, incremental adoption, and rollback strategy before large-scale command rewrites begin.

## Non-Goals

1. Rewriting every command in one PR.
2. Changing CLI behavior or output format. Any differences are regressions unless explicitly approved and documented.
3. Solving the broader import graph problem in this plan. That work is orthogonal and can proceed in parallel.

## Background

1. Typer does not provide native lazy-loading; any lazy-loading in Typer requires custom implementation.
2. Cyclopts provides native lazy-loading and a cleaner API for complex commands.
3. FastMCP (jlowin/fastmcp) completed a full Typer → Cyclopts migration in https://github.com/jlowin/fastmcp/pull/1062 with comprehensive CLI tests. That project is a useful reference for the shape of a Cyclopts CLI and test coverage, not necessarily for incremental adoption.
4. Prefect’s CLI surface area is large and heavily tested, so the migration must be incremental and reversible.

## Plan Summary

We will keep Typer as the default until parity is established, and introduce a parallel Cyclopts entrypoint for migration testing behind a migration toggle. A single registry will govern command discovery and lazy registration in Cyclopts. Non-migrated commands will delegate to Typer. This provides a safe, incremental path with clear escape hatches.

## Migration Toggle (Exact Mechanism)

Toggle: internal environment variable `PREFECT_CLI_IMPL` with allowed values:

1. `typer` (default)
2. `cyclopts` (opt-in)

Wiring (internal-only, not documented for users):

1. Implemented in `src/prefect/cli/__init__.py` (the console entrypoint for `prefect`).
2. The entrypoint reads the env var before importing CLI modules.
3. If `PREFECT_CLI_IMPL=cyclopts`, route to `prefect.cli._cyclopts.app`; otherwise route to `prefect.cli.root.app`.
4. Routing rule from the spike PR remains in place: help/version/completion and non-migrated commands continue to delegate to Typer until parity is guaranteed.

Notes:

1. This replaces any “fast mode” naming; there is no behavior divergence allowed when the toggle is enabled.
2. The optional dependency group should be renamed accordingly (e.g., `cyclopts-cli`) to avoid “fast” language.
3. The exact env var name is internal and can change before a user-facing rollout.

## Phase 0: Entrypoint and Global Flags Parity

Problem: The Typer root callback currently sets up settings, console configuration, logging, and Windows event loop policy. Cyclopts must honor the same behavior and global flags, or behavior will diverge.

Plan:

1. Extract root startup logic into a shared module at `src/prefect/cli/_entrypoint.py`, with a single public entry that accepts a profile name, prompt override, and a console-like interface.
2. Implement equivalent global flags in Cyclopts for `--profile`, `--prompt`, and `--version`, and call into the shared entrypoint.
3. Ensure `prefect --profile <x>` and `prefect --prompt/--no-prompt` behave identically in Typer and Cyclopts modes.

Acceptance:

1. Global flags produce identical behavior and exit codes in both modes.
2. Logging setup and console configuration match existing Typer behavior.

Status (Phase 0):
- [ ] Create `src/prefect/cli/_entrypoint.py` and move shared startup logic from `src/prefect/cli/root.py`.
- [ ] Cyclopts root callback uses `src/prefect/cli/_entrypoint.py`.
- [ ] Parity tests cover `--profile`, `--prompt/--no-prompt`, `--version`.

## Phase 1: Command Registry, Routing, and Lazy Registration

Problem: We need a single source of truth for command registration and a safe, incremental migration path that preserves parity.

Plan:

1. Create a command registry module at `src/prefect/cli/_registry.py` that defines command name, help text, and import target.
2. Cyclopts reads the registry to register commands without importing the modules up front. On invocation, it imports the real implementation and executes it.
3. For commands not yet migrated, the cyclopts handler delegates to Typer with the same arguments.
4. The registry defines which commands are “native cyclopts” vs “delegated to typer” per command group.
5. Routing rule (empirically validated in the spike PR): the entrypoint must delegate to Typer unless the command is explicitly marked as Cyclopts-native. Top-level help/version/completion flags should continue to route to Typer until help output parity is guaranteed.
6. Keep Typer module registration in a single helper at `src/prefect/cli/_typer_loader.py` (used by both entrypoints).

Acceptance:

1. Delegated commands run through Typer and retain current behavior.
2. Help/version/completion remain routed to Typer until Cyclopts help output parity is guaranteed.

Status (Phase 1):
- [ ] Create `src/prefect/cli/_registry.py`.
- [ ] Create `src/prefect/cli/_typer_loader.py` for Typer command registration.
- [ ] Route all non-migrated commands to Typer (no “not implemented” gaps).
- [ ] Add parity tests for top-level help/version routing.

## Phase 2: Incremental Migration of Command Groups

Problem: We need a repeatable migration pattern and an ordering that reduces risk.

Plan:

1. Migrate in small groups, starting with low-risk and high-impact commands.
2. For each group, add a native Cyclopts implementation and flip its registry entry to “native.”
3. Add parity tests and a benchmark entry for each migrated group.

Suggested order:

1. config, profile (low risk, minimal network/server interaction; good for proving parity)
2. server, worker (high-traffic, but still primarily CLI orchestration; strong signal on parity)
3. deploy, flow-run (complex behavior, larger surface area; migrate after pattern is proven)
4. work-pool, work-queue, variable (moderate complexity; depends on client/server plumbing)
5. remaining long-tail commands

Acceptance:

1. Each migrated group has parity tests that validate exit codes and core output.
2. Benchmarks demonstrate expected improvements for help and discovery commands.

Status (Phase 2):
- [ ] Migrate `config` and `profile`.
- [ ] Migrate `server` and `worker`.
- [ ] Migrate `deploy` and `flow-run`.
- [ ] Migrate `work-pool`, `work-queue`, `variable`.
- [ ] Migrate remaining command groups.

## Phase 3: Default Flip and Typer Retirement

Problem: We need a clear path to make Cyclopts the default and retire Typer without breaking users.

Plan:

1. Once all command groups are native and parity tests pass, flip the default to Cyclopts and keep a legacy opt-out toggle.
2. Communicate the default flip and timeline for Typer removal.
3. Remove Typer dependency and legacy code paths after a deprecation period.

Acceptance:

1. Cyclopts is the default CLI and passes the full CLI test suite.
2. Typer can be removed cleanly without functional regressions.

Status (Phase 3):
- [ ] Flip default entrypoint to Cyclopts.
- [ ] Keep a temporary opt-out for one release window.
- [ ] Remove Typer dependency and legacy code.

## Testing Strategy

1. Parity tests for migrated commands should compare exit code and core output fields. If help formatting differs, it must be explicitly approved and documented.
2. Use existing CLI test utilities where possible; prefer invoking `python -m prefect` to ensure tests execute the local code.
3. Keep CLI benchmarks in `benches/cli-bench.toml`, and ensure CI runs both standard and Cyclopts categories.

## Benchmarking Strategy

1. Track `--help`, `--version`, and `config` commands in standard and Cyclopts entrypoints.
2. Add benchmarks for each migrated command group to prevent regressions.
3. Publish results in CI summaries for standard vs Cyclopts CLI.

## Risks and Mitigations

1. Risk: Global flags and startup behavior drift between frameworks.
   Mitigation: Shared entrypoint module and parity tests for `--profile`, `--prompt`, and `--version`.
2. Risk: Command help text diverges.
   Mitigation: Route help/version/completion to Typer until parity is guaranteed; treat differences as regressions unless explicitly approved and documented.
3. Risk: Migration slows due to large surface area.
   Mitigation: Per-group PRs with explicit scope and regression tests.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Unknown command with toggle enabled | Delegate to Typer (error message remains Typer's) |
| Cyclopts not installed, toggle enabled | Error with install hint |
| `--help` / `--version` / completion with toggle enabled | Route to Typer until help parity is guaranteed |
| Partially migrated command group | Route to Typer unless explicitly marked as Cyclopts-native |

## Verification Checklist

### Automated
- [ ] `uv run pytest tests/cli/` passes
- [ ] Type checker passes

### Manual
- [ ] `prefect --help` output matches current CLI
- [ ] `prefect --version` output matches current CLI
- [ ] `prefect --profile <name> ...` selects the correct profile

## References

1. FastMCP migration PR: https://github.com/jlowin/fastmcp/pull/1062
2. Spike PR (Cyclopts entrypoint + delegation pattern): https://github.com/PrefectHQ/prefect/pull/20549
3. Spike PR (Typer lazy-loading): https://github.com/PrefectHQ/prefect/pull/20448
4. CLI benchmarks: `benches/cli-bench.toml`
5. Draft CLI toggle implementation: `src/prefect/cli/__init__.py`
