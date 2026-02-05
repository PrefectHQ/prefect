# Prefect CLI: Cyclopts Migration Plan

## Goal

Migrate the Prefect CLI from Typer to Cyclopts in an incremental, low-risk way that preserves CLI behavior and improves help/discovery startup time. The plan must define command registration, incremental adoption, and rollback strategy before large-scale command rewrites begin.

## Non-Goals

1. Rewriting every command in one PR.
2. Changing CLI behavior or output format beyond acknowledged help formatting differences.
3. Solving the broader import graph problem in this plan. That work is orthogonal and can proceed in parallel.

## Background

1. Typer does not provide native lazy-loading, so Prefect uses custom lazy-loading patterns to improve startup time.
2. Cyclopts provides native lazy-loading and a cleaner API for complex commands.
3. FastMCP (jlowin/fastmcp) completed a full Typer → Cyclopts migration in PR #1062 with comprehensive CLI tests. That project is a useful reference for the shape of a Cyclopts CLI and test coverage, not necessarily for incremental adoption.
4. Prefect’s CLI surface area is large and heavily tested, so the migration must be incremental and reversible.

## Plan Summary

We will keep Typer as the default until parity is established, and introduce Cyclopts behind an opt-in toggle. A single registry will govern command discovery and lazy registration in Cyclopts. Non-migrated commands will delegate to Typer. This provides a safe, incremental path with clear escape hatches.

## Phase 0: Bootstrapping and Global Flags Parity

Problem: The Typer root callback currently sets up settings, console configuration, logging, and Windows event loop policy. Cyclopts must honor the same behavior and global flags, or fast mode will diverge.

Plan:

1. Extract root startup logic into a shared module, e.g. `prefect.cli._bootstrap`, with a single public entry that accepts a profile name, prompt override, and a console-like interface.
2. Implement equivalent global flags in Cyclopts for `--profile`, `--prompt`, and `--version`, and call into the shared bootstrap.
3. Ensure `prefect --profile <x>` and `prefect --prompt/--no-prompt` behave identically in Typer and Cyclopts modes.

Acceptance:

1. Global flags produce identical behavior and exit codes in both modes.
2. Logging setup and console configuration match existing Typer behavior.

## Phase 1: Command Registry and Lazy Registration

Problem: We need a single source of truth for command registration and a safe, incremental migration path.

Plan:

1. Create a command registry module, e.g. `prefect.cli._registry`, that defines command name, help text, and import target.
2. Cyclopts reads the registry to register commands without importing the modules up front. On invocation, it imports the real implementation and executes it.
3. For commands not yet migrated, the cyclopts handler delegates to Typer with the same arguments.
4. The registry defines which commands are “native cyclopts” vs “delegated to typer” per command group.

Acceptance:

1. Cyclopts `--help` renders a full command list without importing all modules.
2. Delegated commands run through Typer and retain current behavior.

## Phase 2: Incremental Migration of Command Groups

Problem: We need a repeatable migration pattern and an ordering that reduces risk.

Plan:

1. Migrate in small groups, starting with low-risk and high-impact commands.
2. For each group, add a native Cyclopts implementation and flip its registry entry to “native.”
3. Add parity tests and a benchmark entry for each migrated group.

Suggested order:

1. config, profile
2. server, worker
3. deploy, flow-run
4. work-pool, work-queue, variable
5. remaining long-tail commands

Acceptance:

1. Each migrated group has parity tests that validate exit codes and core output.
2. Benchmarks demonstrate expected improvements for help and discovery commands.

## Phase 3: Default Flip and Typer Retirement

Problem: We need a clear path to make Cyclopts the default and retire Typer without breaking users.

Plan:

1. Once all command groups are native and parity tests pass, flip the default to Cyclopts and keep a legacy opt-out toggle.
2. Communicate the default flip and timeline for Typer removal.
3. Remove Typer dependency and legacy code paths after a deprecation period.

Acceptance:

1. Cyclopts is the default CLI and passes the full CLI test suite.
2. Typer can be removed cleanly without functional regressions.

## Testing Strategy

1. Parity tests for migrated commands should compare exit code and core output fields, not help formatting.
2. Use existing CLI test utilities where possible; prefer invoking `python -m prefect` to ensure tests execute the local code.
3. Keep CLI benchmarks in `benches/cli-bench.toml`, and ensure CI runs both standard and fast categories.

## Benchmarking Strategy

1. Track `--help`, `--version`, and `config` commands in standard and fast modes.
2. Add benchmarks for each migrated command group to prevent regressions.
3. Publish results in CI summaries for standard vs fast CLI.

## Risks and Mitigations

1. Risk: Global flags and startup behavior drift between frameworks.
   Mitigation: Shared bootstrap module and parity tests for `--profile`, `--prompt`, and `--version`.
2. Risk: Command help text diverges.
   Mitigation: Accept formatting differences but ensure command list coverage and exit code parity.
3. Risk: Migration slows due to large surface area.
   Mitigation: Per-group PRs with explicit scope and regression tests.

## References

1. FastMCP migration PR: https://github.com/jlowin/fastmcp/pull/1062
2. CLI benchmarks: `benches/cli-bench.toml`
3. Draft CLI toggle implementation: `src/prefect/cli/__init__.py`
