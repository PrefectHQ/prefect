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

## Terminology

Each command in the CLI is in one of two states during the migration:

- **migrated**: reimplemented in cyclopts with its own command handler in `src/prefect/cli/_cyclopts/<command>.py`. Cyclopts handles parsing and execution directly.
- **delegated**: registered as a cyclopts command stub that forwards all arguments to the existing typer implementation via `_delegate()`. Behavior is identical to typer-only mode.

A command moves from delegated to migrated by replacing its stub with a real cyclopts implementation and adding parity tests.

```python
# delegated (stub that forwards to typer)
deploy_app = cyclopts.App(name="deploy", help="Create and manage deployments.")
_app.command(deploy_app)

@deploy_app.default
def deploy_default(*tokens: str):
    _delegate("deploy", tokens)

# migrated (real cyclopts implementation)
@config_app.command()
def view(
    *,
    show_defaults: Annotated[bool, cyclopts.Parameter("--show-defaults", negative="--hide-defaults")] = False,
    show_sources: Annotated[bool, cyclopts.Parameter("--show-sources", negative="--hide-sources")] = True,
):
    ...
```

## Plan Summary

We will keep Typer as the default until parity is established, and introduce a parallel Cyclopts entrypoint for migration testing behind an internal migration toggle. Delegated commands will forward to Typer. This provides a safe, incremental path with clear escape hatches.

## Migration Toggle (Exact Mechanism)

Toggle: internal environment variable (not user-facing).

Empirically implemented in #20549:

1. `PREFECT_CLI_FAST=1` enables Cyclopts.
2. Unset uses Typer.

Wiring (internal-only, not documented for users):

1. Implemented in `src/prefect/cli/__init__.py` (the console entrypoint for `prefect`).
2. The entrypoint reads the env var before importing CLI modules.
3. If the toggle is enabled, route to `prefect.cli._cyclopts.app`; otherwise route to `prefect.cli.root.app`.
4. Routing rule from #20549 remains in place: help/version/completion and non-migrated commands continue to delegate to Typer until parity is guaranteed.

Routing code (from #20549):

```python
_USE_CYCLOPTS = os.environ.get("PREFECT_CLI_FAST", "").lower() in ("1", "true")

def app() -> None:
    if _should_delegate_to_typer(sys.argv[1:]):
        load_typer_commands()
        typer_app()
    else:
        cyclopts_app()
```

Notes:

1. This is internal-only and can be renamed before any user-facing rollout.
2. There is no behavior divergence allowed when the toggle is enabled.

## Phase 0: Entrypoint and Global Flags Parity

Problem: The Typer root callback currently sets up settings, console configuration, logging, and Windows event loop policy. Cyclopts must honor the same behavior and global flags, or behavior will diverge.

Plan (implemented in #20549):

1. Mirror Typer's root behavior in `src/prefect/cli/_cyclopts/__init__.py`:
   - profile selection via `prefect.context.use_profile(...)`
   - prompt behavior via `PREFECT_CLI_PROMPT`
   - console setup
   - logging setup
   - Windows event loop policy
2. Ensure `prefect --profile <x>` and `prefect --prompt/--no-prompt` behave identically in Typer and Cyclopts modes (validated by parity tests).

Entrypoint snippet (from #20549):

```python
@_app.meta.default
def _root_callback(..., profile: Optional[str] = None, prompt: Optional[bool] = None):
    ...
    if profile and prefect.context.get_settings_context().profile.name != profile:
        with prefect.context.use_profile(profile, override_environment_variables=True):
            _run_with_settings()
    else:
        _run_with_settings()
```

Acceptance:

1. Global flags produce identical behavior and exit codes in both modes.
2. Logging setup and console configuration match existing Typer behavior.

Scope: Root callback, global flags, console/logging setup. Pattern proven in #20549; to be landed as part of this work.

## Phase 1: Routing and Lazy Registration

Problem: We need a single source of truth for command registration and a safe, incremental migration path that preserves parity.

Plan (implemented in #20549):

1. Cyclopts registers command groups explicitly in `src/prefect/cli/_cyclopts/__init__.py`.
2. For commands not yet migrated, the Cyclopts handler delegates to Typer with the same arguments.
3. Routing rule: the entrypoint delegates to Typer unless the command is migrated. Top-level help/version/completion flags route to Typer until help output parity is guaranteed.
4. Typer module registration is centralized in `src/prefect/cli/_typer_loader.py` (used by both entrypoints).

Delegation mechanism (from #20549):

```python
def _delegate(command: str, tokens: tuple[str, ...]) -> None:
    load_typer_commands()
    typer_app([command, *tokens], standalone_mode=False)
```

Acceptance:

1. Delegated commands run through Typer and retain current behavior.
2. Help/version/completion remain routed to Typer until Cyclopts help output parity is guaranteed.

Scope: Toggle wiring, delegation stubs for all commands, typer loader module. Pattern proven in #20549; to be landed as part of this work.

## Phase 2: Incremental Migration of Command Groups

Problem: We need a repeatable migration pattern and an ordering that reduces risk.

Plan:

1. Migrate in small groups, starting with low-risk and high-impact commands.
2. For each group, replace the delegated stub with a migrated cyclopts implementation and wire it into `src/prefect/cli/_cyclopts/__init__.py` (pattern proven in #20549).
3. Add parity tests and a benchmark entry for each migrated group.

Migration template for a command group (aligned with #20549):

1. Create `src/prefect/cli/_cyclopts/<command>.py` with Cyclopts app + commands.
2. Import and register the new Cyclopts app in `src/prefect/cli/_cyclopts/__init__.py`.
3. Ensure delegation still works for any subcommands not migrated.
4. Add parity tests in `tests/cli/test_cyclopts_parity.py` for exit codes and core output.
5. Add/update benchmarks in `benches/cli-bench.toml`.

Worked example (Config → Cyclopts, abridged from #20549):

```python
# Typer (today)
@config_app.command()
def view(...): ...

# Cyclopts (target)
@config_app.command()
def view(
    show_defaults: Annotated[bool, cyclopts.Parameter("--show-defaults", negative="--hide-defaults")] = False,
    ...
): ...
```

Suggested order (all top-level command groups):

**Wave 1** — low risk, minimal network/server interaction, good for proving parity:
- `config` (view, set, unset, validate)
- `profile` (ls, create, delete, rename, populate-defaults, use, inspect)
- `version`

**Wave 2** — high-traffic, primarily CLI orchestration:
- `server` (start, services)
- `worker` (start)
- `shell` (serve, watch)

**Wave 3** — complex behavior, larger surface area:
- `deploy` (entrypoint, init)
- `flow-run` (ls, inspect, cancel, delete, logs, execute)
- `flow` (ls, serve)
- `deployment` (ls, inspect, run, schedule, pause, resume, delete, apply, build)

**Wave 4** — moderate complexity, server-backed CRUD:
- `work-pool` (ls, create, delete, inspect, pause, resume, set-concurrency-limit, clear-concurrency-limit, preview, get-default-base-job-template, update)
- `work-queue` (ls, create, delete, inspect, pause, resume, set-concurrency-limit, clear-concurrency-limit)
- `variable` (ls, get, set, unset, inspect)
- `block` (ls, create, delete, inspect, register)
- `concurrency-limit` / `global-concurrency-limit`

**Wave 5** — remaining commands:
- `cloud` (login, logout, workspace ls/set/create, webhook, asset, ip-allowlist)
- `artifact` (ls, inspect, delete)
- `automation` (ls, inspect, delete, pause, resume, create)
- `event` (stream, emit)
- `task` / `task-run`
- `api` (raw HTTP verbs)
- `dashboard` (open)
- `dev` (start, build-image, container, api-ref)
- `transfer`
- `sdk` (generate)

Acceptance:

1. Each migrated group has parity tests that validate exit codes and core output.
2. Benchmarks demonstrate expected improvements for help and discovery commands.

## Phase 3: Default Flip and Typer Retirement

Problem: We need a clear path to make Cyclopts the default and retire Typer without breaking users.

Plan:

1. Once all command groups are migrated and parity tests pass, flip the default to Cyclopts and keep a legacy opt-out toggle.
2. Communicate the default flip and timeline for Typer removal.
3. Remove Typer dependency and legacy code paths after a deprecation period.

Acceptance:

1. Cyclopts is the default CLI and passes the full CLI test suite.
2. Typer can be removed cleanly without functional regressions.

Scope: Flip default, deprecation period, remove typer dependency.

## Testing Strategy

### Existing test infrastructure: `invoke_and_assert`

The current CLI test suite uses `invoke_and_assert` (`src/prefect/testing/cli.py`), which wraps typer's `CliRunner` to test commands in-process. There are ~950 call sites across 35 test files.

**Key constraint (empirically verified):** `invoke_and_assert` cannot test cyclopts commands through typer's `CliRunner`. With `PREFECT_CLI_FAST=1`, `from prefect.cli import app` returns a plain function (the cyclopts entrypoint), not a `Typer` instance. Typer's `CliRunner` raises `AttributeError: 'function' object has no attribute '_add_completion'`.

**During migration (Phases 0–2) and beyond:** `invoke_and_assert` now supports both frameworks via an internal `CycloptsCliRunner`. When `PREFECT_CLI_FAST=1`, it uses the cyclopts runner; otherwise it uses typer's `CliRunner`. The ~950 call sites do not need to change.

### `CycloptsCliRunner` (`src/prefect/testing/cli.py`)

Analogous to Click's `CliRunner`, this provides in-process invocation of the cyclopts CLI with proper I/O isolation. Cyclopts does not ship a built-in test runner ([issue #238](https://github.com/BrianPugh/cyclopts/issues/238) was closed by design), so we maintain our own.

**Design:**

1. **TTY-emulating StringIO** — a `StringIO` subclass with `isatty() -> True`. Rich Console resolves `sys.stdout` dynamically via its `file` property, so redirecting sys.stdout to this buffer means all Console output is captured. The TTY emulation makes `Console.is_interactive` return True, enabling `Confirm.ask()` / `Prompt.ask()` to work correctly — matching real terminal behavior.

2. **State isolation** — saves and restores `sys.stdout`, `sys.stderr`, `sys.stdin`, `os.environ["COLUMNS"]`, and the global `_cli.console` in a `try/finally` block. Not thread-safe (mutates interpreter globals), but safe with pytest-xdist which forks separate worker processes.

3. **Exit code handling** — catches `SystemExit` to extract exit codes. For delegated commands, `_delegate()` converts Click exceptions (`ClickException`, `Exit`, `Abort`) to `SystemExit` with the correct code.

4. **Wide terminal** — sets `COLUMNS=500` to prevent Rich from wrapping long lines, which would cause brittle output assertions.

**Usage:**

```python
from prefect.testing.cli import CycloptsCliRunner

runner = CycloptsCliRunner()
result = runner.invoke(["config", "view"])
assert result.exit_code == 0
assert "PREFECT_API_URL" in result.stdout

# With interactive input
result = runner.invoke(["profile", "create", "my-profile"], input="y\n")
assert result.exit_code == 0
```

The `CycloptsResult` returned by `invoke()` is compatible with typer's `Result` (has `.stdout`, `.stderr`, `.output`, `.exit_code`, `.exception`), so `invoke_and_assert` and `check_contains` work without changes.

**Known limitations:**

1. Exit code 2 vs 1: typer/click returns 2 for missing required arguments; cyclopts returns 1. Tests asserting `expected_code=2` will need updating when commands are migrated.
2. Async tests using `run_sync_in_worker_thread`: the runner redirects process-global `sys.stdout`, which can interact poorly with multi-threaded async test patterns. A small number of delegated-command tests may need adjustment.

### Parity tests: `run_cli`

Parity tests are a migration-time safety net that verify both CLI modes produce identical results. They use a subprocess-based `run_cli` utility (`tests/cli/test_cyclopts_parity.py`):

```python
def run_cli(args: list[str], fast: bool = False) -> subprocess.CompletedProcess:
    """Run the prefect CLI as a subprocess."""
    env = os.environ.copy()
    if fast:
        env["PREFECT_CLI_FAST"] = "1"
    else:
        env.pop("PREFECT_CLI_FAST", None)
    return subprocess.run(
        [sys.executable, "-m", "prefect"] + args,
        capture_output=True,
        text=True,
        env=env,
    )
```

`run_cli` is subprocess-based because it needs to compare the two entrypoints end-to-end (toggle routing, import paths, process lifecycle). It is not a replacement for `invoke_and_assert` — it exists only to validate parity during the migration and will be removed when typer is retired.

Parity test pattern (from #20549):

```python
def test_version_output_parity():
    typer = run_cli(["--version"], fast=False)
    cyclopts = run_cli(["--version"], fast=True)
    assert typer.returncode == 0
    assert cyclopts.returncode == 0
    assert normalize_output(typer.stdout) == normalize_output(cyclopts.stdout)
```

### Testing during migration

For each migrated command group, add parity tests that validate:
1. Exit codes match between typer and cyclopts modes.
2. Core output fields match (setting names, data values, error messages).
3. Help formatting differences, if any, are explicitly documented.

## Benchmarking Strategy

CLI startup benchmarks already run in CI via [python-cli-bench](https://github.com/zzstoatzz/python-cli-bench) (`.github/workflows/benchmarks.yaml`). The workflow uses hyperfine to compare head vs base on every PR, with results posted to the GitHub step summary.

1. Add migrated commands to `benches/cli-bench.toml` as they are migrated (currently tracks `--help`, `--version`, `version`).
2. Add a `cyclopts` category to `benches/cli-bench.toml` that runs the same commands with `PREFECT_CLI_FAST=1` so CI compares both entrypoints side by side.
3. Use the existing CI comparison (Welch's t-test, delta %) to catch regressions.

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
| Partially migrated command group | Delegated commands route to Typer; only migrated commands use cyclopts |

## Verification Checklist

### Automated
- `uv run pytest tests/cli/` passes (existing tests via typer)
- `uv run pytest tests/cli/test_cyclopts_parity.py` passes (parity tests via subprocess)
- Type checker passes

### Manual
- `prefect --help` output matches current CLI
- `prefect --version` output matches current CLI
- `prefect --profile <name> ...` selects the correct profile

## References

1. FastMCP migration PR: https://github.com/jlowin/fastmcp/pull/1062
2. Cyclopts entrypoint + delegation spike: #20549
3. Typer lazy-loading spike: #20448
4. CLI benchmark config: `benches/cli-bench.toml`
5. CLI benchmark CI workflow: `.github/workflows/benchmarks.yaml`
6. Benchmark harness: [python-cli-bench](https://github.com/zzstoatzz/python-cli-bench)
7. Toggle implementation: `src/prefect/cli/__init__.py`
