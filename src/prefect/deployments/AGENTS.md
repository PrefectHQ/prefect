# Deployments

YAML-driven configuration for packaging, publishing, and triggering flow runs from infrastructure.

## Purpose & Scope

Handles deployment lifecycle: initializing projects, building/pushing deployment artifacts, and triggering remote flow runs. Does NOT manage flow execution itself — that lives in `flow_engine.py` and `task_engine.py`.

## Entry Points & Contracts

- `runner.py` → `deploy()` — programmatic deployment creation from `Flow` objects
- `flow_runs.py` → `run_deployment()` / `arun_deployment()` — trigger a run of an existing deployment
- `base.py` → `initialize_project()` — scaffold `prefect.yaml` in a project directory
- `steps/core.py` → `run_step()` / `run_steps()` — execute lifecycle steps defined in `prefect.yaml`

## Steps System

Steps are YAML entries in `build`, `push`, or `pull` blocks of `prefect.yaml`. Each step maps to a Python function imported at runtime. The `requires` keyword auto-installs missing packages before import.

Step outputs are templated into subsequent steps via `{{ step-id.key }}`.

Built-in steps:
- `steps/pull.py` — `git_clone`, `set_working_directory`, `pull_from_remote_storage`
- `steps/utility.py` — `run_shell_script`, `pip_install_requirements`

## Pitfalls

- **Windows shell mode**: `run_shell_script` always uses `asyncio.create_subprocess_shell` on Windows (`sys.platform == "win32"`), regardless of the `shell` parameter. This ensures cmd.exe built-ins (`echo`, `dir`, `set`, etc.) work. On non-Windows, `shell=False` (default) uses `create_subprocess_exec` with `shlex.split`.
- **Step ID namespace**: `id` and `requires` are reserved keywords — do not use them as step output keys.
- **Step import side effects**: steps are imported dynamically; packages listed in `requires` are installed into the current environment at execution time.
