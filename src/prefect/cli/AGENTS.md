# CLI

Prefect command-line interface, powered by **cyclopts**.

## Key Contracts

- **Use `rich` for all output.** Console output via `rich.console`, tables via `rich.table`, progress bars via `rich.progress`. Always use `exit_with_error` for error exits.
- **Support JSON output whenever possible.** Commands should have a `--json` flag or equivalent for machine-readable output. Any diagnostic or informational `print()` calls must be suppressed when JSON output is active — mixing human-readable text with the JSON payload breaks machine consumers.
- **Excluded from `prefect-client`** — the entire `cli/` directory is stripped during the client package build.

## Structure

- `_app.py` — Root `cyclopts.App` and session-level flags (`--profile`, `--prompt`)
- Top-level files — One file per command group: `flow.py`, `task.py`, `server.py`, `worker.py`, `block.py`, `deployment.py`, `variable.py`, `work_pool.py`, etc.
- `deploy/` — `prefect deploy` subcommand — the most complex subcommand with its own internal module structure
- `cloud/` — `prefect cloud` subcommands (login, workspace, webhooks, IP allowlists)
- `transfer/` — `prefect transfer` subcommands
- `experimental.py` — `prefect experimental` command group; register new subcommands via lazy string references (`experimental_app.command("prefect.cli.module:app_object", name="...")`) to defer imports until the subcommand is invoked
- `_utilities.py`, `_prompts.py`, `_server_utils.py`, `_cloud_utils.py`, `_worker_utils.py` — Internal helpers (prefixed with `_`)
- `flow_runs_watching.py` — Command-specific support module for `flow-run watch`; provides `watch_flow_run()` and `FlowRunFormatter`. Not prefixed with `_` — command-specific helpers may omit the prefix.

## Testing

```bash
uv run pytest tests/cli/ -x -n4         # All CLI tests
uv run pytest tests/cli/test_flow.py    # Single command group
uv run pytest tests/cli/deploy/         # Deploy subcommand tests
```

## Related

- `tests/cli/` → CLI tests mirror this directory structure
