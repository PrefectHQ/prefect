# Prefect Experimental Plugin System — Startup Hooks (Spec)

**Goal:** Ship an **experimental** plugin system that lets third-party packages run a **startup hook** before Prefect CLI/agents/workers do any work (e.g., obtain short-lived AWS credentials and set env vars).

**Scope (beta):** *One* hook: `setup_environment`. Implementation lives under `prefect/_experimental/plugins/…`. API is explicitly unstable and namespaced as experimental.

---

## 1) Package layout (new)

```
prefect/
  _experimental/
    plugins/
      __init__.py
      manager.py          # pluggy manager + async bridge + enable/disable policy
      spec.py             # HookContext, SetupResult, HookSpec
      apply.py            # safe env application + redaction, diagnostics
      diagnostics.py      # list/diagnose helpers
      config.py           # feature flag, timeouts, ordering, allow/deny
```

**Public import (experimental):**

* `prefect._experimental.plugins.spec`
* `prefect._experimental.plugins.manager`
* `prefect._experimental.plugins.apply`

Everything else is internal.

---

## 2) Configuration & feature flag

* **Env flag:** `PREFECT_EXPERIMENTS_PLUGINS_ENABLED=1` (default: off).
  If not set, the system does nothing and loads no plugins.
* **Optional allow/deny lists:**

  * `PREFECT_PLUGINS_ALLOW` (comma-sep entry point names)
  * `PREFECT_PLUGINS_DENY`
* **Timeouts:** `PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS` (default `20`)
* **Strict mode:** `PREFECT_PLUGINS_STRICT=1` → any plugin error marked `required=True` aborts Prefect startup.
* **Safe mode:** `PREFECT_PLUGINS_SAFE_MODE=1` → load plugins but do not call hooks (for debugging).

---

## 3) Hook API (experimental)

```python
# prefect/_experimental/plugins/spec.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Callable
from datetime import datetime

# Bump this when breaking the experimental hook contract
PREFECT_PLUGIN_API_VERSION = "0.1"

@dataclass(slots=True)
class HookContext:
    prefect_version: str
    api_url: str | None
    # Logger factory returns a stdlib logger; plugins should use this.
    logger_factory: Callable[[str], "logging.Logger"]
    # Future: async Prefect client getter, settings snapshot, etc.

@dataclass(slots=True)
class SetupResult:
    env: Mapping[str, str]                        # e.g. AWS_* variables
    note: Optional[str] = None                    # short, non-secret human hint
    expires_at: Optional[datetime] = None         # for diagnostics / refresh UIs
    required: bool = False                        # if True and hook fails -> abort (in strict mode)

class HookSpec(Protocol):
    async def setup_environment(self, *, ctx: HookContext) -> Optional[SetupResult]:
        """Prepare process environment for Prefect and its children.
        Return None to indicate 'no changes'.
        Must not print secrets or write to disk by default.
        """
```

---

## 4) Plugin discovery & registration

* **Entry point group:** `prefect.plugins`
  (Though the runtime lives in `_experimental`, we purposefully use the final group name; we can alias later.)
* Plugins are classes/objects exposing `setup_environment`.
* Optional attribute on plugin object: `PREFECT_PLUGIN_API_REQUIRES` (PEP 440 range; default `>=0.1,<1`).

**Implementation:**

```python
# prefect/_experimental/plugins/manager.py
import pluggy, importlib.metadata as md, logging, anyio

PM_PROJECT_NAME = "prefect-experimental"
EP_GROUP = "prefect.plugins"

def build_manager(hookspecs) -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PM_PROJECT_NAME)
    pm.add_hookspecs(hookspecs)
    return pm

def load_entry_point_plugins(pm, *, allow: set[str] | None, deny: set[str] | None, logger):
    for ep in md.entry_points(group=EP_GROUP):
        if allow and ep.name not in allow: 
            continue
        if deny and ep.name in deny: 
            continue
        try:
            plugin = ep.load()
            # version fence (best effort)
            requires = getattr(plugin, "PREFECT_PLUGIN_API_REQUIRES", ">=0.1,<1")
            # Optional: validate `requires` against PREFECT_PLUGIN_API_VERSION
            pm.register(plugin, name=ep.name)
        except Exception:
            logger.exception("Failed to load plugin %s", ep.name)

async def call_async_hook(pm: pluggy.PluginManager, hook_name: str, **kwargs):
    """Call a hook that may return coroutines; gather results and exceptions per plugin."""
    hook = getattr(pm.hook, hook_name)
    results = []
    for impl in hook.get_hookimpls():
        fn = impl.function
        try:
            res = fn(**kwargs)
            if anyio.iscoroutine(res):
                res = await res
            results.append((impl.plugin_name, res, None))
        except Exception as exc:
            results.append((impl.plugin_name, None, exc))
    return results
```

---

## 5) Applying results safely

```python
# prefect/_experimental/plugins/apply.py
import os, logging
from contextlib import contextmanager

REDACT_KEYS = ("SECRET", "TOKEN", "PASSWORD", "KEY")

def redact(key: str, value: str) -> str:
    k = key.upper()
    if any(tag in k for tag in REDACT_KEYS):
        return "••••••"
    return value if len(value) <= 64 else value[:20] + "…"

def apply_setup_result(result, logger):
    """Apply env changes to current process; never log secrets."""
    for k, v in (result.env or {}).items():
        os.environ[str(k)] = str(v)
    note = result.note or ""
    logger.info(
        "plugin env applied%s",
        f" — {note}" if note else "",
    )

def summarize_env(env: dict[str, str]) -> dict[str, str]:
    return {k: redact(k, v) for k, v in env.items()}
```

---

## 6) Orchestration: running `setup_environment` at startup

* **Call site(s) (minimal to start):**

  * CLI entry (before Typer command execution): `prefect/cli/__init__.py` or the main entry wrapper.
  * Worker/Agent entrypoints (before contacting APIs or importing AWS libs).
* Respect feature flags; skip entirely if disabled.

```python
# prefect/_experimental/plugins/config.py
import os

def enabled() -> bool:
    return os.getenv("PREFECT_EXPERIMENTS_PLUGINS_ENABLED") == "1"

def timeout_seconds() -> float:
    return float(os.getenv("PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS", "20"))

def lists():
    allow = os.getenv("PREFECT_PLUGINS_ALLOW")
    deny  = os.getenv("PREFECT_PLUGINS_DENY")
    return (
        set(a.strip() for a in allow.split(",")) if allow else None,
        set(d.strip() for d in deny.split(",")) if deny else None,
    )

def strict() -> bool:
    return os.getenv("PREFECT_PLUGINS_STRICT") == "1"

def safe_mode() -> bool:
    return os.getenv("PREFECT_PLUGINS_SAFE_MODE") == "1"
```

```python
# prefect/_experimental/plugins/diagnostics.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class SetupSummary:
    plugin: str
    env_preview: dict[str, str]
    note: str | None
    expires_at: datetime | None
    error: str | None
```

```python
# prefect/_experimental/plugins/__init__.py
import anyio, logging
from . import config
from .manager import build_manager, load_entry_point_plugins, call_async_hook
from .spec import HookSpec, HookContext, PREFECT_PLUGIN_API_VERSION
from .apply import apply_setup_result, summarize_env
from .diagnostics import SetupSummary

async def run_startup_hooks(ctx: HookContext) -> list[SetupSummary]:
    logger = ctx.logger_factory("prefect.plugins")
    if not config.enabled():
        return []
    pm = build_manager(HookSpec)
    allow, deny = config.lists()
    load_entry_point_plugins(pm, allow=allow, deny=deny, logger=logger)

    summaries: list[SetupSummary] = []
    if config.safe_mode():
        return summaries

    with anyio.move_on_after(config.timeout_seconds()) as cancel_scope:
        results = await call_async_hook(pm, "setup_environment", ctx=ctx)
    if cancel_scope.cancel_called:
        logger.warning("Plugin setup timed out after %.1fs", config.timeout_seconds())

    for name, res, err in results:
        if err:
            summaries.append(SetupSummary(name, {}, None, None, error=str(err)))
            continue
        if res is None:
            summaries.append(SetupSummary(name, {}, None, None, error=None))
            continue
        try:
            apply_setup_result(res, logger)
            summaries.append(
                SetupSummary(
                    name,
                    summarize_env(dict(res.env)),
                    res.note,
                    res.expires_at,
                    error=None,
                )
            )
        except Exception as e:
            summaries.append(SetupSummary(name, {}, None, None, error=str(e)))

    # strict failure policy
    if config.strict():
        for name, res, err in results:
            if err:
                raise SystemExit(f"[plugins] required plugin '{name}' failed: {err}")
            if getattr(res, "required", False) and not res.env:
                raise SystemExit(f"[plugins] required plugin '{name}' returned no environment")
    return summaries
```

---

## 7) Wiring into Prefect startup

**CLI** (single call early in process):

```python
# prefect/cli/_bootstrap.py (new) OR in existing CLI entry main
from prefect._experimental.plugins import run_startup_hooks
from prefect._experimental.plugins.spec import HookContext
from prefect.logging import get_logger

def _logger_factory(name: str):
    return get_logger(name)

def _make_ctx() -> HookContext:
    from prefect import __version__
    from prefect.settings import PREFECT_API_URL
    return HookContext(
        prefect_version=__version__,
        api_url=str(PREFECT_API_URL.value()),
        logger_factory=_logger_factory,
    )

def run_with_plugins(main_callable):
    async def _setup():
        await run_startup_hooks(_make_ctx())
    import anyio; anyio.run(_setup)
    return main_callable()
```

Then wrap CLI main:

```python
# prefect/cli/__init__.py
from ._bootstrap import run_with_plugins
def app_main():
    # existing Typer app invocation…
    ...
if __name__ == "__main__":
    run_with_plugins(app_main)
```

**Workers/Agents:** call the same `_setup()` before network calls in their `main()` functions.

---

## 8) Minimal CLI diagnostics

Add a hidden experimental command:

```
prefect experimental plugins diagnose
```

* Prints whether experimental plugins are enabled.
* Lists discovered entry points.
* Shows per-plugin last `SetupSummary` (env names only, redacted values; note; expires_at; error).

You may wire this into an existing “experimental” CLI group.

---

## 9) Example third-party plugin (for contributors)

**pyproject.toml**

```toml
[project]
name = "prefect-aws-setup"
version = "0.1.0"
dependencies = ["prefect>=3.4", "pluggy>=1.5", "botocore>=1.34"]

[project.entry-points."prefect.plugins"]
aws_setup = "prefect_aws_setup:Plugin"
```

**prefect_aws_setup/**init**.py**

```python
from __future__ import annotations
import os
from datetime import timezone
import botocore.session
from prefect._experimental.plugins.spec import HookContext, SetupResult

PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"

class Plugin:
    async def setup_environment(self, *, ctx: HookContext):
        role_arn = os.getenv("PREFECT_AWS_SETUP_ROLE_ARN")
        if not role_arn:
            return None

        bc = botocore.session.Session(profile=os.getenv("PREFECT_AWS_SETUP_PROFILE"))
        sts = bc.create_client("sts", region_name=os.getenv("AWS_REGION") or "us-east-1")
        resp = sts.assume_role(RoleArn=role_arn, RoleSessionName="prefect-setup", DurationSeconds=int(os.getenv("PREFECT_AWS_SETUP_DURATION", "3600")))
        c = resp["Credentials"]
        return SetupResult(
            env={
                "AWS_ACCESS_KEY_ID": c["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": c["SecretAccessKey"],
                "AWS_SESSION_TOKEN": c["SessionToken"],
                "AWS_REGION": os.getenv("AWS_REGION") or "us-east-1",
            },
            note=f"assumed {role_arn.split('/')[-1]}",
            expires_at=c["Expiration"].astimezone(timezone.utc),
            required=bool(os.getenv("PREFECT_AWS_SETUP_REQUIRED")),
        )
```

---

## 10) Behavior & guarantees

* **Ordering:** As returned by `importlib.metadata.entry_points`; we do **not** guarantee order. Future: accept `PREFECT_PLUGINS_ORDER` (comma-sep).
* **Idempotence:** Plugins should be idempotent; last write wins on env keys.
* **Isolation:** Exceptions are captured per plugin; never crash the process unless strict mode + required.
* **No secrets in logs:** All diagnostics redact value by key name heuristics.
* **Async OK:** Hooks may be `async`. The bridge awaits them.
* **Timeouts:** Global timeout (move-on-after) around the entire hook phase.
* **Opt-in:** Entire subsystem gated by `PREFECT_EXPERIMENTS_PLUGINS_ENABLED=1`.

---

## 11) Testing plan (acceptance criteria)

**Unit tests (pytest):**

1. **Feature flag off:** no discovery, no calls.
2. **Discovery:** fake entry points with two plugins; both loaded.
3. **Async hook:** plugin returns coroutine; env applied.
4. **Error handling:** one plugin raises; the other succeeds; summaries reflect both.
5. **Redaction:** `AWS_SECRET_ACCESS_KEY` redacted in summaries/logs.
6. **Timeout:** long-sleeping plugin -> timeout log; summaries exist; process continues.
7. **Strict mode failure:** plugin returns `required=True` then raises → `SystemExit`.
8. **Deny/allow list:** only allowed plugin runs.
9. **Safe mode:** loads but does not execute hooks.
10. **Version fence:** plugin with incompatible `PREFECT_PLUGIN_API_REQUIRES` is skipped (or logged).

**Integration tests:**

* Wrap a dummy CLI command and assert env visible within the process after startup.

---

## 12) Documentation (short, experimental)

* New page: **“Experimental Plugins (Beta)”** under Developer Guides.

  * Enable flag, safety notes, API versioning.
  * Quickstart with the example AWS plugin.
  * FAQ (ordering, logging, secrets, strict mode).

---

## 13) Security & support notes

* Experimental; do not load untrusted plugins.
* Provide `PREFECT_PLUGINS_DENY` to quarantine known-bad plugin names.
* Offer `--no-plugins` equivalent via not setting the flag.
* Support asks for `prefect experimental plugins diagnose` output.

---

## 14) Future-proofing (not in this PR)

* Additional hooks: `refresh_environment`, `cli_commands`, `register_blocks`, etc.
* Per-hook timeouts; per-plugin ordering/priorities.
* Persistent cache of last summaries (file or API).
* Structured error types for better UX.

---

## 15) Definition of Done

* Code merged under `prefect/_experimental/plugins/…`.
* CLI/worker entrypoints call `run_startup_hooks` when `PREFECT_EXPERIMENTS_PLUGINS_ENABLED=1`.
* At least 10 unit tests above are implemented and pass.
* Hidden `prefect experimental plugins diagnose` prints usable output.
* Docs page added with clear “experimental/unstable” banner.
