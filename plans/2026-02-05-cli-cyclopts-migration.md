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
- `server` (start, services, status)
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

**Status:** Phase 2 complete. Full test suite passes under `PREFECT_CLI_FAST=1`:
- `tests/cli/`: 1189 passed, 8 skipped (4 typer-specific, 1 windows, 1 TODO, 2 color)
- `tests/events/client/cli/test_automations.py`: 46 passed

### Current file layout

```
src/prefect/cli/
├── _cyclopts/                    ← 29 files, ~11,850 lines (new impl, becomes the CLI)
│   ├── __init__.py               ← app, root callback, command registrations
│   ├── _utilities.py             ← exit helpers, exception handling
│   ├── deployment.py, deploy.py, server.py, ...  ← command modules
│
├── *.py                          ← ~20 typer command files, ~9,200 lines (to be deleted)
│   ├── root.py                   ← typer app, root callback (to be deleted)
│   ├── _typer_loader.py          ← typer registration (to be deleted)
│   ├── _types.py                 ← typer-specific types (to be deleted)
│   ├── _utilities.py             ← typer utilities (to be deleted)
│
├── _prompts.py                   ← SHARED (14 cyclopts files import from it)
├── _server_utils.py              ← SHARED (cyclopts server.py imports from it)
├── _cloud_utils.py               ← SHARED (cyclopts cloud.py imports from it)
├── _worker_utils.py              ← SHARED (cyclopts worker.py imports from it)
├── _transfer_utils.py            ← SHARED (cyclopts transfer.py imports from it)
├── flow_runs_watching.py         ← SHARED (cyclopts deployment.py imports from it)
├── deploy/                       ← SHARED business logic (_config, _core, _schedules, etc.)
├── transfer/                     ← SHARED business logic (_dag, _exceptions, _migratable_resources/)
│
├── __init__.py                   ← toggle/routing logic (to be simplified)
│
├── cloud/                        ← typer cloud commands (to be deleted, cyclopts cloud.py replaces them)
├── profile.py                    ← typer profile (to be deleted, BUT exports ConnectionStatus/check_server_connection used by cyclopts)
├── shell.py                      ← typer shell (to be deleted, BUT exports run_shell_process used by cyclopts)
```

### Shared modules that survive

These contain framework-agnostic business logic. Cyclopts commands already import from them. They stay in `src/prefect/cli/` unchanged:

| module | consumers | what it provides |
|---|---|---|
| `_prompts.py` (887 lines) | 14 cyclopts files | `confirm`, `prompt_select_from_table`, `prompt` |
| `_server_utils.py` (411 lines) | cyclopts `server.py` | `SERVER_PID_FILE_NAME`, `_run_in_background`, `_run_in_foreground`, `prestart_check`, `_run_all_services`, etc. |
| `_cloud_utils.py` (431 lines) | cyclopts `cloud.py` | `login_with_browser`, `prompt_for_account_and_workspace`, `check_key_is_valid_for_login`, etc. |
| `_worker_utils.py` (133 lines) | cyclopts `worker.py` | `_load_worker_class`, `_check_work_pool_paused`, etc. |
| `_transfer_utils.py` (121 lines) | cyclopts `transfer.py` | `collect_resources`, `execute_transfer`, etc. |
| `flow_runs_watching.py` (191 lines) | cyclopts `deployment.py` | `watch_flow_run` |
| `deploy/` subpackage | cyclopts `deploy.py` | `_run_multi_deploy`, `_run_single_deploy`, `_config`, `_schedules`, etc. |
| `transfer/` subpackage | cyclopts `transfer.py` | `TransferDAG`, `TransferSkipped`, `_migratable_resources/` |

### Business logic to extract before deletion

Two typer command files export non-CLI functions that cyclopts commands import. These need to be moved to shared modules before the typer files can be deleted:

| typer file | exports used by cyclopts | move to |
|---|---|---|
| `profile.py` | `ConnectionStatus`, `check_server_connection` | `_profile_utils.py` (new, ~80 lines) |
| `shell.py` | `run_shell_process` | `_shell_utils.py` (new, ~100 lines) |

### PR breakdown

**PR 1: flip the default** (~30 lines changed)

Invert the toggle so cyclopts is the default and typer is the opt-in escape hatch.

- `src/prefect/cli/__init__.py`: change `_USE_CYCLOPTS` to `_USE_TYPER`, default to cyclopts
  - `_USE_TYPER = os.environ.get("PREFECT_CLI_TYPER", "").lower() in ("1", "true")`
  - invert `_should_delegate_to_typer` → only used when `_USE_TYPER` is set
  - when `_USE_TYPER` is not set, go straight to `_cyclopts_app()`
- `src/prefect/testing/cli.py`: invert the runner selection logic
- update env var references in CI, tests, benchmarks (`PREFECT_CLI_FAST` → removed, `PREFECT_CLI_TYPER` → opt-in)
- files touched: `src/prefect/cli/__init__.py`, `src/prefect/testing/cli.py`, `.github/workflows/python-tests.yaml`, `benches/cli-bench.toml`, ~10 test files that reference `PREFECT_CLI_FAST` or `_USE_CYCLOPTS`

Validation: `uv run pytest tests/cli/ -n4` passes (now running cyclopts by default). `PREFECT_CLI_TYPER=1 uv run pytest tests/cli/ -n4` also passes (typer fallback).

Estimated: ~30 lines of logic changes + ~40 lines of env var renames across 16 files.

**PR 2: extract shared business logic from typer files** (~200 lines moved)

Move non-CLI functions out of typer command files so those files can be cleanly deleted.

- create `src/prefect/cli/_profile_utils.py`: move `ConnectionStatus` enum and `check_server_connection()` from `profile.py`
- create `src/prefect/cli/_shell_utils.py`: move `run_shell_process()` from `shell.py`
- update imports in:
  - `src/prefect/cli/_cyclopts/profile.py`: `from prefect.cli._profile_utils import ...`
  - `src/prefect/cli/_cyclopts/shell.py`: `from prefect.cli._shell_utils import ...`
  - `src/prefect/cli/profile.py`: `from prefect.cli._profile_utils import ...` (typer version still works while escape hatch exists)
  - `src/prefect/cli/shell.py`: `from prefect.cli._shell_utils import ...`

Estimated: ~200 lines moved, ~20 import fixups. Zero behavior change.

**PR 3: move `_cyclopts/` contents up to `cli/`** (~800 lines of import path changes)

Rename the cyclopts modules to become the primary CLI modules. This is the wholesale file path migration.

Approach: `git mv` each file, then find-and-replace all import paths.

- `src/prefect/cli/_cyclopts/__init__.py` → merge into `src/prefect/cli/__init__.py` (the app, root callback, and command registrations become the sole entrypoint)
- `src/prefect/cli/_cyclopts/_utilities.py` → `src/prefect/cli/_utilities.py` (replaces the typer one)
- `src/prefect/cli/_cyclopts/deployment.py` → `src/prefect/cli/deployment.py` (replaces the typer one)
- ... same pattern for all 27 command modules

Import paths to rewrite:
- 84 occurrences of `prefect.cli._cyclopts` across 31 source files → `prefect.cli`
- ~17 test files that monkeypatch `prefect.cli._cyclopts.*` → `prefect.cli.*`
- `import prefect.cli._cyclopts as _cli` in every command file → `import prefect.cli as _cli`

The `_cyclopts/` directory is deleted after all moves.

Estimated: ~0 new lines of logic. ~800 lines of mechanical import path changes across ~50 files.

**PR 4: delete typer command files and infrastructure** (~-11,000 lines)

Remove all typer-only code now that cyclopts is the sole implementation.

Delete:
- typer command files: `root.py`, `server.py`, `worker.py`, `shell.py` (now just the extracted util), `config.py`, `profile.py` (now just the extracted util), `flow_run.py`, `flow.py`, `deployment.py`, `work_pool.py`, `work_queue.py`, `variable.py`, `block.py`, `concurrency_limit.py`, `global_concurrency_limit.py`, `artifact.py`, `experimental.py`, `events.py`, `task.py`, `task_run.py`, `api.py`, `dashboard.py`, `dev.py`, `sdk.py`
- typer infrastructure: `_typer_loader.py`, `_types.py`
- typer cloud commands: `cloud/__init__.py`, `cloud/webhook.py`, `cloud/asset.py`, `cloud/ip_allowlist.py`
- typer automations: `src/prefect/events/cli/automations.py`
- test-time migration scaffolding: `tests/cli/test_cyclopts_parity.py`, `tests/cli/test_cyclopts_runner.py`

Simplify:
- `src/prefect/cli/__init__.py`: remove `_USE_TYPER`, `_should_delegate_to_typer`, `_DELEGATE_FLAGS`, `_CYCLOPTS_COMMANDS`, `_FLAGS_WITH_VALUES`. The entrypoint just calls `app()` directly.
- `src/prefect/testing/cli.py`: remove typer `CliRunner` branch from `invoke_and_assert`, remove `_USE_CYCLOPTS` checks. `CycloptsCliRunner` becomes the only runner (can be renamed to just `CliRunner`).
- CI: remove `PREFECT_CLI_TYPER` matrix leg, remove typer-specific test skips

Estimated: ~-11,000 lines deleted, ~-200 lines of routing/toggle logic removed, ~50 lines of test simplification.

**PR 5: remove typer dependency** (~10 lines)

- `pyproject.toml`: remove `typer` from dependencies
- `client/pyproject.toml`: parallel change if typer is listed there
- verify nothing else imports typer: `rg "import typer" src/prefect/`

This is kept as a separate PR because it's the point of no return — if anything was missed, this is where it surfaces.

Estimated: ~10 lines.

### Summary

| PR | description | lines changed (est.) | risk |
|---|---|---|---|
| 1 | flip default | +70 / -70 | low — tests already pass under cyclopts |
| 2 | extract shared business logic | +220 / -20 | low — pure refactor, no behavior change |
| 3 | move `_cyclopts/` up to `cli/` | +400 / -400 | medium — large rename, but mechanical |
| 4 | delete typer code | +50 / -11,200 | low — everything already tested without typer |
| 5 | remove typer dependency | +0 / -10 | low — final validation |

**Total: ~-11,000 net lines removed.** ~750 lines of mechanical rename work. No new application logic.

PRs 1-2 can be done independently (no ordering dependency between them). PR 3 depends on PR 2. PR 4 depends on PR 3. PR 5 depends on PR 4.

### Acceptance criteria

1. `uv run pytest tests/cli/ tests/events/client/cli/ -n4` passes with no `PREFECT_CLI_*` env vars set (cyclopts is the default).
2. No references to `prefect.cli._cyclopts` remain in the codebase.
3. No references to `PREFECT_CLI_FAST` or `PREFECT_CLI_TYPER` remain.
4. `typer` is not in `pyproject.toml` dependencies.
5. `rg "import typer" src/prefect/` returns zero matches.

## Testing Strategy

### Test infrastructure: `invoke_and_assert`

The CLI test suite uses `invoke_and_assert` (`src/prefect/testing/cli.py`), which wraps an internal `CycloptsCliRunner` to test commands in-process. There are ~950 call sites across 35 test files.

**During the migration (Phases 0–2):** `invoke_and_assert` supported both frameworks — `CycloptsCliRunner` when `PREFECT_CLI_FAST=1`, typer's `CliRunner` otherwise. After Phase 3, the typer branch will be removed and `CycloptsCliRunner` becomes the sole runner.

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

### Phase 2 risks (resolved)

1. ~~Risk: Global flags and startup behavior drift between frameworks.~~
   Resolved: Parity tests validated identical behavior; full test suite passes under cyclopts.
2. ~~Risk: Command help text diverges.~~
   Resolved: All commands migrated, help output validated through test suite.
3. ~~Risk: Migration slows due to large surface area.~~
   Resolved: All command groups migrated across waves 1–5.

### Phase 3 risks

1. Risk: File rename PR (PR 3) breaks downstream forks or tools that import from `prefect.cli._cyclopts`.
   Mitigation: `_cyclopts` is a private module (leading underscore), not public API. No external consumers expected.
2. Risk: Monkeypatch targets in tests break after rename.
   Mitigation: Systematic `rg` sweep for all `_cyclopts` references before and after rename.
3. Risk: Removing typer reveals hidden imports we missed.
   Mitigation: PR 5 (remove dependency) is a separate, small PR specifically to catch this.

## Verification Checklist

### After Phase 3 completion
- `uv run pytest tests/cli/ tests/events/client/cli/ -n4` passes with no env vars
- `rg "prefect.cli._cyclopts" src/ tests/` returns zero matches
- `rg "PREFECT_CLI_FAST|PREFECT_CLI_TYPER" src/ tests/ .github/` returns zero matches
- `rg "import typer" src/prefect/` returns zero matches
- `prefect --help`, `prefect --version`, `prefect config view` work correctly
- `prefect --profile <name> config view` selects the correct profile

## References

1. FastMCP migration PR: https://github.com/jlowin/fastmcp/pull/1062
2. Cyclopts entrypoint + delegation spike: #20549
3. Typer lazy-loading spike: #20448
4. CLI benchmark config: `benches/cli-bench.toml`
5. CLI benchmark CI workflow: `.github/workflows/benchmarks.yaml`
6. Benchmark harness: [python-cli-bench](https://github.com/zzstoatzz/python-cli-bench)
7. Toggle implementation: `src/prefect/cli/__init__.py`
