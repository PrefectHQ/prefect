# Cyclopts CLI Migration

This directory contains the Prefect CLI implementation using cyclopts. We're migrating from typer to cyclopts for better lazy loading and startup performance.

## Enabling

Set `PREFECT_CLI_FAST=1` to use the cyclopts CLI during migration:

```bash
PREFECT_CLI_FAST=1 prefect --help
```

Requires the `fast-cli` extra:
```bash
pip install prefect[fast-cli]
```

## Migration Pattern

### 1. Create the cyclopts command module

Create a new file in `src/prefect/cli/_cyclopts/` with the command implementation:

```python
"""
Command name - native cyclopts implementation.
"""
from __future__ import annotations

import sys
from typing import Annotated

import cyclopts

command_app = cyclopts.App(name="command", help="Command description.")


@command_app.command()
def subcommand(
    arg: Annotated[str, cyclopts.Parameter(help="Argument description")],
    *,
    flag: Annotated[bool, cyclopts.Parameter("--flag", alias="-f", help="Flag description")] = False,
):
    """Subcommand docstring shown in help."""
    # Lazy imports - only load when command runs
    import prefect.settings
    from prefect.some_module import some_function

    # Command implementation
    ...
```

### 2. Key differences from typer

| Typer | Cyclopts |
|-------|----------|
| `@app.command()` | `@app.command()` or `@app.command(name="name")` |
| `typer.Option("--flag", "-f")` | `cyclopts.Parameter("--flag", alias="-f")` |
| `typer.Option("--show/--hide")` | `cyclopts.Parameter("--show", negative="--hide")` |
| `typer.Argument()` | `cyclopts.Parameter()` (positional by default) |
| `typer.Exit(code)` | `sys.exit(code)` |

### 3. Lazy import pattern

**Critical**: All heavy imports must be inside command functions, not at module level:

```python
# BAD - imports at module level defeat lazy loading
import prefect.settings
from prefect.client import get_client

@app.command()
def my_command():
    ...

# GOOD - imports inside command function
@app.command()
def my_command():
    import prefect.settings
    from prefect.client import get_client
    ...
```

### 4. Register in __init__.py

Add the command to `_cyclopts/__init__.py`:

```python
# --- command (native cyclopts) ---
from prefect.cli._cyclopts.command import command_app
app.command(command_app)
```

### 5. Remove typer delegation

If there was a typer delegation placeholder, remove it when adding the native implementation.

## Migration Status

Commands implemented in native cyclopts:
- [x] config (set, unset, validate, view)

Commands delegating to typer (to be migrated):
- [ ] deploy
- [ ] flow-run
- [ ] worker
- [ ] block
- [ ] profile
- [ ] server
- [ ] cloud
- [ ] work-pool
- [ ] variable

Commands showing "not implemented" (low priority):
- api, artifact, concurrency-limit, dashboard, deployment, dev, events, flow,
  global-concurrency-limit, shell, task, task-run, work-queue, automations, transfer

## Benchmarking

Run benchmarks to verify performance:

```bash
uv run cli-bench -C benches/cli-bench.toml run
```

Compare cyclopts vs typer CLI:
- `prefect --help` should be faster with cyclopts (lazy loading benefit)
- Individual commands should be similar (both do full imports)
