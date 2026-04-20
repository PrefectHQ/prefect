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

**Status**: Phase 2 complete. Full test suite passes under `PREFECT_CLI_FAST=1` (1189 passed, 8 skipped). All command groups have native cyclopts implementations.

Problem: Cyclopts implementations live in `src/prefect/cli/_cyclopts/` alongside the typer originals. We need to make cyclopts the sole CLI, promote the `_cyclopts/` files to be the primary modules, and delete typer.

### Current Layout

```
src/prefect/cli/
├── _cyclopts/                    ← 29 files, ~11,850 lines (new impl)
│   ├── __init__.py               ← app, root callback, command registrations
│   ├── _utilities.py             ← exit helpers, exception handling
│   └── <command>.py              ← one per command group
│
├── <command>.py                  ← ~20 typer command files, ~9,200 lines (to delete)
├── root.py, _typer_loader.py    ← typer infrastructure (to delete)
├── cloud/                        ← typer cloud subpackage (to delete)
│
├── __init__.py                   ← toggle/routing logic (to simplify)
│
├── _prompts.py                   ← shared — 14 cyclopts files import from it
├── _server_utils.py              ← shared — cyclopts server.py imports from it
├── _cloud_utils.py               ← shared — cyclopts cloud.py imports from it
├── _worker_utils.py              ← shared — cyclopts worker.py imports from it
├── _transfer_utils.py            ← shared — cyclopts transfer.py imports from it
├── flow_runs_watching.py         ← shared — cyclopts deployment.py imports from it
├── deploy/                       ← shared business logic (cyclopts deploy.py imports from it)
└── transfer/                     ← shared business logic (cyclopts transfer.py imports from it)
```

Two typer command files export non-CLI functions that the cyclopts side imports:
- `profile.py` exports `ConnectionStatus`, `check_server_connection` → used by `_cyclopts/profile.py`
- `shell.py` exports `run_shell_process` → used by `_cyclopts/shell.py`

When the cyclopts files move up to replace the typer files, these functions move into the new `profile.py` and `shell.py` directly — no intermediate utility modules needed.

### 3a: Flip the Default

Invert the toggle so cyclopts is the default and typer is the opt-in escape hatch.

- `src/prefect/cli/__init__.py`: `_USE_TYPER = os.environ.get("PREFECT_CLI_TYPER", "").lower() in ("1", "true")`; default path goes straight to `_cyclopts_app()`
- `src/prefect/testing/cli.py`: invert runner selection
- Update env var references across CI, tests, benchmarks: `PREFECT_CLI_FAST` → removed, `PREFECT_CLI_TYPER` → opt-in

**Status**:
- [ ] `src/prefect/cli/__init__.py` — invert toggle
- [ ] `src/prefect/testing/cli.py` — invert runner selection
- [ ] `.github/workflows/python-tests.yaml` — update CI matrix
- [ ] `benches/cli-bench.toml` — update benchmark env vars
- [ ] ~10 test files referencing `PREFECT_CLI_FAST` or `_USE_CYCLOPTS`
- [ ] `uv run pytest tests/cli/ -n4` passes (cyclopts default)
- [ ] `PREFECT_CLI_TYPER=1 uv run pytest tests/cli/ -n4` passes (typer fallback)

### 3b: Promote Cyclopts to Primary + Delete Typer

Move `_cyclopts/` contents up to `cli/`, absorb shared functions from the typer files they replace, delete all typer code, remove the toggle.

**Rename**: `git mv` each `_cyclopts/<command>.py` to `cli/<command>.py`, replacing the typer version. `_cyclopts/__init__.py` merges into `cli/__init__.py`. `_cyclopts/_utilities.py` replaces `cli/_utilities.py`.

**Absorb shared functions**: When `_cyclopts/profile.py` becomes `cli/profile.py`, add `ConnectionStatus` and `check_server_connection` directly into it (moved from the typer `profile.py` being replaced). Same for `run_shell_process` into the new `shell.py`.

**Import path rewrite**: 84 occurrences of `prefect.cli._cyclopts` across 31 source files → `prefect.cli`. ~17 test files with monkeypatch targets.

**Delete**:
- All typer command files (`root.py`, `_typer_loader.py`, `_types.py`, typer `_utilities.py`, typer `cloud/`, `events/cli/automations.py`)
- Toggle/routing logic (`_should_delegate_to_typer`, `_CYCLOPTS_COMMANDS`, `_DELEGATE_FLAGS`)
- Parity test scaffolding (`test_cyclopts_parity.py`, `test_cyclopts_runner.py`)
- Typer branch from `invoke_and_assert` in `testing/cli.py`
- `PREFECT_CLI_TYPER` env var and CI matrix leg
- `typer` from `pyproject.toml` dependencies (and `client/pyproject.toml` if listed)

**Status**:
- [ ] `git mv` all `_cyclopts/` files up to `cli/`
- [ ] Absorb `ConnectionStatus`/`check_server_connection` into new `profile.py`
- [ ] Absorb `run_shell_process` + helpers into new `shell.py`
- [ ] Rewrite all `prefect.cli._cyclopts` import paths (~50 files)
- [ ] Delete typer command files (~-11,000 lines)
- [ ] Delete typer infrastructure (`root.py`, `_typer_loader.py`, `_types.py`)
- [ ] Simplify `cli/__init__.py` — remove toggle, routing, delegate flags
- [ ] Simplify `testing/cli.py` — remove typer runner branch
- [ ] Remove CI matrix leg and env var references
- [ ] Remove `typer` from dependencies
- [ ] `rg "prefect.cli._cyclopts" src/ tests/` returns zero matches
- [ ] `rg "PREFECT_CLI_FAST|PREFECT_CLI_TYPER" src/ tests/ .github/` returns zero matches
- [ ] `rg "import typer" src/prefect/` returns zero matches
- [ ] `uv run pytest tests/cli/ tests/events/client/cli/ -n4` passes

## Testing Strategy

### Test infrastructure: `invoke_and_assert`

The CLI test suite uses `invoke_and_assert` (`src/prefect/testing/cli.py`), which wraps an internal `CycloptsCliRunner` to test commands in-process. There are ~950 call sites across 35 test files.

During the migration (Phases 0–2), `invoke_and_assert` supported both frameworks — `CycloptsCliRunner` when `PREFECT_CLI_FAST=1`, typer's `CliRunner` otherwise. After Phase 3, the typer branch is removed and `CycloptsCliRunner` becomes the sole runner.

### `CycloptsCliRunner` (`src/prefect/testing/cli.py`)

Analogous to Click's `CliRunner`, this provides in-process invocation of the cyclopts CLI with proper I/O isolation. Cyclopts does not ship a built-in test runner ([issue #238](https://github.com/BrianPugh/cyclopts/issues/238) was closed by design), so we maintain our own.

**Design:**

1. **TTY-emulating StringIO** — a `StringIO` subclass with `isatty() -> True`. Rich Console resolves `sys.stdout` dynamically via its `file` property, so redirecting sys.stdout to this buffer means all Console output is captured. The TTY emulation makes `Console.is_interactive` return True, enabling `Confirm.ask()` / `Prompt.ask()` to work correctly — matching real terminal behavior.

2. **State isolation** — saves and restores `sys.stdout`, `sys.stderr`, `sys.stdin`, `os.environ["COLUMNS"]`, and the global `_cli.console` in a `try/finally` block. Not thread-safe (mutates interpreter globals), but safe with pytest-xdist which forks separate worker processes.

3. **Exit code handling** — catches `SystemExit` to extract exit codes.

4. **Wide terminal** — sets `COLUMNS=500` to prevent Rich from wrapping long lines, which would cause brittle output assertions.

## Risks and Mitigations

### Phase 2 risks (resolved)

1. ~~Risk: Global flags and startup behavior drift between frameworks.~~
   Resolved: Parity tests validated identical behavior; full test suite passes under cyclopts.
2. ~~Risk: Command help text diverges.~~
   Resolved: All commands migrated, help output validated through test suite.

### Phase 3 risks

1. Risk: File rename breaks downstream forks or tools that import from `prefect.cli._cyclopts`.
   Mitigation: `_cyclopts` is a private module (leading underscore), not public API.
2. Risk: Monkeypatch targets in tests break after rename.
   Mitigation: Systematic `rg` sweep for all `_cyclopts` references before and after.
3. Risk: Removing typer reveals hidden imports.
   Mitigation: `rg "import typer" src/prefect/` as final validation.

## Verification Checklist

### After Phase 3 completion
- `uv run pytest tests/cli/ tests/events/client/cli/ -n4` passes with no env vars
- `rg "prefect.cli._cyclopts" src/ tests/` returns zero matches
- `rg "PREFECT_CLI_FAST|PREFECT_CLI_TYPER" src/ tests/ .github/` returns zero matches
- `rg "import typer" src/prefect/` returns zero matches
- `prefect --help`, `prefect --version`, `prefect config view` work correctly

## References

1. FastMCP migration PR: https://github.com/jlowin/fastmcp/pull/1062
2. Cyclopts entrypoint + delegation spike: #20549
3. Typer lazy-loading spike: #20448
4. CLI benchmark config: `benches/cli-bench.toml`
5. CLI benchmark CI workflow: `.github/workflows/benchmarks.yaml`
6. Benchmark harness: [python-cli-bench](https://github.com/zzstoatzz/python-cli-bench)
7. Toggle implementation: `src/prefect/cli/__init__.py`
