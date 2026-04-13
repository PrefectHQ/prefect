"""
Orchestrator for per-node and per-wave dbt execution.

This module provides:
- ExecutionMode: Constants for execution mode selection
- PrefectDbtOrchestrator: Executes dbt builds with wave or per-node execution
"""

import argparse
import dataclasses
import json as _json
import os
import sys
import threading
from collections import deque
from contextlib import ExitStack, nullcontext
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

from cachetools import LFUCache
from dbt.artifacts.resources.types import NodeType

from prefect import task as prefect_task
from prefect.artifacts import create_markdown_artifact
from prefect.concurrency.sync import concurrency as prefect_concurrency
from prefect.context import AssetContext, FlowRunContext
from prefect.logging import get_logger, get_run_logger
from prefect.settings import PREFECT_CLIENT_SERVER_VERSION_CHECK_ENABLED
from prefect.settings.context import temporary_settings
from prefect.task_runners import ProcessPoolTaskRunner
from prefect.tasks import MaterializingTask
from prefect_dbt.core._artifacts import (
    ASSET_NODE_TYPES,
    create_asset_for_node,
    create_summary_markdown,
    get_compiled_code_for_node,
    get_upstream_assets_for_node,
    write_run_results_json,
)
from prefect_dbt.core._cache import build_cache_policy_for_node
from prefect_dbt.core._executor import DbtCoreExecutor, DbtExecutor, ExecutionResult
from prefect_dbt.core._freshness import (
    compute_freshness_expiration,
    filter_stale_nodes,
    run_source_freshness,
)
from prefect_dbt.core._manifest import (
    DbtNode,
    ExecutionWave,
    ManifestParser,
    resolve_selection,
)
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import format_resource_id

logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Execution mode for dbt orchestration.

    PER_WAVE: Each wave is a single `dbt build` invocation containing all
        nodes in the wave.  Lower overhead, but a single failure marks the
        entire wave as failed and retries are not per-node.

    PER_NODE: Each node is a separate Prefect task with individual retries
        and concurrency control.  Requires `run_build()` to be called
        inside a `@flow`.
    """

    PER_NODE = "per_node"
    PER_WAVE = "per_wave"


class TestStrategy(Enum):
    """Strategy for executing dbt test nodes.

    IMMEDIATE: Tests are interleaved with models in the execution DAG.
        Kahn's algorithm naturally places each test in the wave after
        all of its parent models complete.  This is the default,
        matching `dbt build` semantics.

    DEFERRED: All model waves execute first, then all tests execute
        together in a final wave.

    SKIP: Tests are excluded from execution.
    """

    __test__ = False  # prevent pytest collection

    IMMEDIATE = "immediate"
    DEFERRED = "deferred"
    SKIP = "skip"


# ---------------------------------------------------------------
# extra_cli_args validation tables
# ---------------------------------------------------------------

_BLOCKED_FLAGS: dict[str, str] = {
    "--select": (
        "The orchestrator resolves selection at the manifest level and passes "
        "nodes as unique-ID selectors; a second CLI-level --select conflicts. "
        "Use the 'select' parameter of run_build() instead."
    ),
    "--models": (
        "Alias for --select. The orchestrator resolves selection at the "
        "manifest level. Use the 'select' parameter of run_build() instead."
    ),
    "--exclude": (
        "The orchestrator resolves exclusion at the manifest level; a CLI-level "
        "--exclude conflicts. Use the 'exclude' parameter of run_build() instead."
    ),
    "--selector": (
        "References a YAML selector that would override the orchestrator's "
        "resolved node set."
    ),
    "--indirect-selection": (
        "Hardcoded to 'empty' in PER_WAVE mode so the orchestrator controls "
        "test scheduling via TestStrategy; a user override would break "
        "IMMEDIATE/DEFERRED behaviour."
    ),
    "--project-dir": (
        "Set from settings.project_dir in the executor; overriding "
        "desynchronizes the orchestrator's path handling."
    ),
    "--target-path": (
        "Set from settings.target_path and used for manifest resolution; "
        "overriding desynchronizes manifest resolution."
    ),
    "--profiles-dir": (
        "Managed via settings.resolve_profiles_yml(); bypassing breaks "
        "temporary profile-file resolution."
    ),
    "--log-level": (
        "Set to 'none' for console output in the executor; the orchestrator "
        "deliberately silences dbt's console output and captures logs via "
        "callbacks."
    ),
}

_FIRST_CLASS_FLAGS: dict[str, str] = {
    "--full-refresh": "run_build(full_refresh=True)",
    "--target": "run_build(target='...')",
    "--threads": "DbtCoreExecutor(threads=N)",
    "--defer": "DbtCoreExecutor(defer=True)",
    "--defer-state": "DbtCoreExecutor(defer_state_path=Path(...))",
    "--favor-state": "DbtCoreExecutor(favor_state=True)",
    "--state": "DbtCoreExecutor(state_path=Path(...))",
}

_CAVEAT_FLAGS: dict[str, str] = {
    "--resource-type": (
        "Filters resource types at the CLI level; passing '--resource-type model' "
        "to a wave that includes tests (via TestStrategy.IMMEDIATE) would "
        "silently drop those tests."
    ),
    "--exclude-resource-type": (
        "Filters resource types at the CLI level; may silently drop tests "
        "scheduled by TestStrategy.IMMEDIATE."
    ),
    "--fail-fast": (
        "In PER_WAVE mode dbt stops the wave on first failure, potentially "
        "leaving nodes in a state the orchestrator hasn't tracked. Safe in "
        "PER_NODE mode since each invocation is a single node."
    ),
}


def _build_extra_cli_args_parser() -> tuple[
    argparse.ArgumentParser, dict[str, tuple[str, str]]
]:
    """Build an ArgumentParser that detects blocked, first-class, and caveat flags.

    Using argparse handles `--flag=value`, `--flag value`, and `-s value`
    forms natively.  Returns the parser and a mapping from argparse dest
    to `(canonical_flag, category)` for error/warning lookup.
    """
    p = argparse.ArgumentParser(add_help=False)
    dest_to_info: dict[str, tuple[str, str]] = {}

    def _add(flags: list[str], dest: str, category: str) -> None:
        p.add_argument(*flags, dest=dest, nargs="?", const=True, default=None)
        dest_to_info[dest] = (flags[0], category)

    # Blocked flags (short aliases grouped with their long forms)
    _add(["--select", "-s"], "select", "blocked")
    _add(["--models", "-m"], "models", "blocked")
    _add(["--exclude"], "exclude", "blocked")
    _add(["--selector"], "selector", "blocked")
    _add(["--indirect-selection"], "indirect_selection", "blocked")
    _add(["--project-dir"], "project_dir", "blocked")
    _add(["--target-path"], "target_path", "blocked")
    _add(["--profiles-dir"], "profiles_dir", "blocked")
    _add(["--log-level"], "log_level", "blocked")

    # First-class flags
    _add(["--full-refresh"], "full_refresh", "first_class")
    _add(["--target", "-t"], "target", "first_class")
    _add(["--threads"], "threads", "first_class")
    _add(["--defer"], "defer", "first_class")
    _add(["--defer-state"], "defer_state", "first_class")
    _add(["--favor-state"], "favor_state", "first_class")
    _add(["--state"], "state", "first_class")

    # Caveat flags
    _add(["--resource-type"], "resource_type", "caveat")
    _add(["--exclude-resource-type"], "exclude_resource_type", "caveat")
    _add(["--fail-fast", "-x"], "fail_fast", "caveat")

    return p, dest_to_info


_EXTRA_CLI_ARGS_PARSER, _DEST_TO_INFO = _build_extra_cli_args_parser()


def _validate_extra_cli_args(extra_cli_args: list[str]) -> None:
    """Validate extra_cli_args against blocked, first-class, and caveat flags.

    Uses `argparse.parse_known_args` to correctly handle `--flag=value`,
    `--flag value`, and short-flag forms.

    Raises:
        ValueError: If any blocked or first-class flag is found.
    """
    known, _ = _EXTRA_CLI_ARGS_PARSER.parse_known_args(extra_cli_args)

    for dest, value in vars(known).items():
        if value is None:
            continue
        flag, category = _DEST_TO_INFO[dest]

        if category == "blocked":
            raise ValueError(
                f"Cannot pass '{flag}' via extra_cli_args: {_BLOCKED_FLAGS[flag]}"
            )
        if category == "first_class":
            raise ValueError(
                f"Cannot pass '{flag}' via extra_cli_args; use "
                f"{_FIRST_CLASS_FLAGS[flag]} instead."
            )
        if category == "caveat":
            logger.warning(
                "extra_cli_args contains '%s': %s", flag, _CAVEAT_FLAGS[flag]
            )


# Map executable node types to their dbt CLI commands.
_NODE_COMMAND = {
    NodeType.Model: "run",
    NodeType.Seed: "seed",
    NodeType.Snapshot: "snapshot",
    NodeType.Test: "test",
}
# NodeType.Unit was added in dbt-core 1.8; guard for older versions.
_UNIT_TYPE = getattr(NodeType, "Unit", None)
if _UNIT_TYPE is not None:
    _NODE_COMMAND[_UNIT_TYPE] = "test"

# Resource types excluded from caching by default.
_DEFAULT_EXCLUDE_RESOURCE_TYPES: frozenset[NodeType] = frozenset(
    t for t in (NodeType.Test, NodeType.Snapshot, _UNIT_TYPE) if t is not None
)

# Keep _TEST_NODE_TYPES for failure-propagation logic (not user-configurable).
_TEST_NODE_TYPES = frozenset(t for t in (NodeType.Test, _UNIT_TYPE) if t is not None)


@dataclasses.dataclass(frozen=True)
class CacheConfig:
    """Configuration for cross-run caching in PER_NODE execution mode.

    Pass an instance to `PrefectDbtOrchestrator(cache=CacheConfig(...))`
    to enable caching.  `None` (the default) disables caching entirely.
    """

    expiration: timedelta | None = None
    result_storage: Any | str | Path | None = None
    key_storage: Any | str | Path | None = None
    use_source_freshness_expiration: bool = False
    exclude_materializations: frozenset[str] = frozenset({"incremental"})
    exclude_resource_types: frozenset[NodeType] = _DEFAULT_EXCLUDE_RESOURCE_TYPES


@dataclasses.dataclass(frozen=True)
class BuildPlan:
    """Result of a dry-run plan showing what `run_build()` would execute.

    Returned by `PrefectDbtOrchestrator.plan`.  All fields are
    read-only so the plan can be safely logged, serialised, or compared
    across invocations.

    Attributes:
        waves: Execution waves in topological order.  Each wave contains
            nodes that can execute in parallel.
        node_count: Total number of nodes across all waves.
        cache_predictions: Per-node cache prediction when caching is
            configured.  Maps `node.unique_id` to `"hit"`,
            `"miss"`, or `"excluded"`.  `None` when caching is
            not configured.
        skipped_nodes: Nodes that were filtered out by selectors or
            source-freshness checks.  Maps `node.unique_id` to a
            result dict with `status` and `reason` keys.
        estimated_parallelism: Width of the largest wave — the maximum
            number of nodes that could execute concurrently.
    """

    waves: tuple[ExecutionWave, ...]
    node_count: int
    cache_predictions: dict[str, str] | None
    skipped_nodes: dict[str, dict[str, Any]]
    estimated_parallelism: int

    def __str__(self) -> str:
        lines: list[str] = []
        lines.append(
            f"BuildPlan: {self.node_count} node(s) in {len(self.waves)} wave(s)"
            f"  |  max parallelism = {self.estimated_parallelism}"
        )
        lines.append("")

        # Wave breakdown
        for wave in self.waves:
            lines.append(f"  Wave {wave.wave_number} ({len(wave.nodes)} node(s)):")
            for node in wave.nodes:
                parts: list[str] = [f"    - {node.unique_id}"]
                tag_parts: list[str] = []
                if node.resource_type is not None:
                    tag_parts.append(node.resource_type.value)
                if node.materialization:
                    tag_parts.append(node.materialization)
                if tag_parts:
                    parts.append(f"[{', '.join(tag_parts)}]")
                if self.cache_predictions and node.unique_id in self.cache_predictions:
                    prediction = self.cache_predictions[node.unique_id]
                    parts.append(f"(cache: {prediction})")
                lines.append(" ".join(parts))

        # Cache summary
        if self.cache_predictions:
            hits = sum(1 for v in self.cache_predictions.values() if v == "hit")
            misses = sum(1 for v in self.cache_predictions.values() if v == "miss")
            excluded = sum(
                1 for v in self.cache_predictions.values() if v == "excluded"
            )
            lines.append("")
            lines.append(
                f"  Cache: {hits} hit(s), {misses} miss(es), {excluded} excluded"
            )

        # Skipped nodes
        if self.skipped_nodes:
            lines.append("")
            lines.append(f"  Skipped ({len(self.skipped_nodes)}):")
            for nid, info in self.skipped_nodes.items():
                reason = info.get("reason", "unknown")
                lines.append(f"    - {nid}: {reason}")

        return "\n".join(lines)


_LOG_EMITTERS = {
    "debug": lambda log, msg: log.debug(msg),
    "info": lambda log, msg: log.info(msg),
    "warning": lambda log, msg: log.warning(msg),
    "error": lambda log, msg: log.error(msg),
}

# Bound process-pool dedupe state to avoid unbounded growth while retaining
# frequently repeated global messages.
_GLOBAL_LOG_DEDUPE_MAX_KEYS = 10_000

_DBT_GLOBAL_LOGGER_NAMES = frozenset(
    {
        "prefect.task_runs.dbt_orchestrator_global",
    }
)


def _emit_log_messages(
    log_messages: dict[str, list[tuple[str, str]]] | None,
    node_id: str,
    target_logger: Any,
) -> None:
    """Emit captured dbt log messages for *node_id* to a Prefect logger.

    Only messages keyed by the given *node_id* are emitted.  Each message
    is emitted at the level it was captured at.
    """
    if not log_messages:
        return
    for level, msg in log_messages.get(node_id, []):
        emitter = _LOG_EMITTERS.get(level, _LOG_EMITTERS["info"])
        emitter(target_logger, msg)


def _dbt_global_log_dedupe_processor_factory():
    """Build a process-pool message processor that drops duplicate dbt global logs."""
    seen_messages: LFUCache[tuple[str, str, int, str], bool] = LFUCache(
        maxsize=_GLOBAL_LOG_DEDUPE_MAX_KEYS
    )

    def _processor(message_type: str, message_payload: Any):
        if message_type != "log" or not isinstance(message_payload, dict):
            return message_type, message_payload

        logger_name = message_payload.get("name")
        flow_run_id = message_payload.get("flow_run_id")
        level = message_payload.get("level")
        message = message_payload.get("message")

        if (
            not isinstance(logger_name, str)
            or logger_name not in _DBT_GLOBAL_LOGGER_NAMES
            or not isinstance(flow_run_id, str)
            or not isinstance(level, int)
            or not isinstance(message, str)
        ):
            return message_type, message_payload

        dedupe_key = (flow_run_id, logger_name, level, message)
        if seen_messages.get(dedupe_key):
            return None
        seen_messages[dedupe_key] = True
        return message_type, message_payload

    return _processor


def _configure_process_pool_subprocess_message_processors(
    task_runner: ProcessPoolTaskRunner,
    processor_factories: list[Any],
) -> bool:
    """Configure process-pool message processors when the runner supports it."""

    try:
        task_runner.subprocess_message_processor_factories = processor_factories
    except (AttributeError, TypeError):
        try:
            task_runner.set_subprocess_message_processor_factories(processor_factories)
        except (AttributeError, TypeError):
            return False
        return True

    return True


class _DbtNodeError(Exception):
    """Raised inside per-node tasks to trigger Prefect retries.

    Carries execution details so the orchestrator can build a proper
    error result after all retries are exhausted.

    Implements `__reduce__` so the exception survives pickle round-trips
    across the `ProcessPoolTaskRunner` process boundary.
    """

    def __init__(
        self,
        execution_result: ExecutionResult,
        timing: dict[str, Any],
        invocation: dict[str, Any],
    ):
        self.execution_result = execution_result
        self.timing = timing
        self.invocation = invocation
        msg = (
            str(execution_result.error) if execution_result.error else "dbt node failed"
        )
        super().__init__(msg)

    def __reduce__(self):
        return (type(self), (self.execution_result, self.timing, self.invocation))


class PrefectDbtOrchestrator:
    """Orchestrate dbt builds wave-by-wave or per-node.

    Wires together ManifestParser (Phase 1), resolve_selection (Phase 2),
    and DbtExecutor (Phase 3) to execute a full dbt build in topological
    wave order.

    Supports two execution modes:

    - **PER_WAVE** (default): Each wave is a single `dbt build` invocation.
      Lower overhead but coarser failure granularity.
    - **PER_NODE**: Each node is a separate Prefect task with individual
      retries and concurrency control.  Requires `run_build()` to be
      called inside a `@flow`.

    Args:
        settings: PrefectDbtSettings instance (created with defaults if None)
        manifest_path: Explicit path to manifest.json (auto-detected if None)
        executor: DbtExecutor implementation (DbtCoreExecutor created if None)
        threads: Number of dbt threads (forwarded to DbtCoreExecutor)
        state_path: Path for --state flag
        defer: Whether to pass --defer flag
        defer_state_path: Path for --defer-state flag
        favor_state: Whether to pass --favor-state flag
        execution_mode: `ExecutionMode.PER_WAVE` or `ExecutionMode.PER_NODE`.
            Raises `ValueError` for unrecognized values.
        retries: Number of retries per node (PER_NODE mode only)
        retry_delay_seconds: Delay between retries in seconds
        concurrency: Concurrency limit.  A string names an existing Prefect
            global concurrency limit; an int sets the max_workers on the
            ProcessPoolTaskRunner used for parallel node execution.
        task_runner_type: Task runner class to use for PER_NODE execution.
            Defaults to `ProcessPoolTaskRunner`.
        cache: A `CacheConfig` instance to enable cross-run caching for
            PER_NODE mode.  When not None, unchanged nodes are skipped on
            subsequent runs.  `None` (default) disables caching entirely.
            Only supported with `execution_mode=ExecutionMode.PER_NODE`.
        test_strategy: Controls when dbt test nodes execute.
            `TestStrategy.IMMEDIATE` (default) interleaves tests with
            models in the DAG (each test runs in the wave after its
            parent models), matching `dbt build` semantics.
            `TestStrategy.DEFERRED` runs all tests after all model waves.
            `TestStrategy.SKIP` excludes tests entirely.
        create_summary_artifact: When True, create a Prefect markdown
            artifact summarising the build results at the end of
            `run_build()`.  Requires an active flow run context.
        include_compiled_code: When True, include compiled SQL in
            asset descriptions (PER_NODE mode only).
        write_run_results: When True, write a dbt-compatible
            `run_results.json` to the target directory after
            `run_build()`.
        disable_assets: Global override to suppress Prefect asset
            creation for dbt node runs.  When True, no
            `MaterializingTask` instances are created regardless of
            per-node configuration.  Defaults to False for backwards
            compatibility.
        hooks: Optional mapping of lifecycle hook names to callables.
            Hook exceptions are logged and never interrupt orchestration.

    Example:

    ```python
    @flow
    def run_dbt_build():
        orchestrator = PrefectDbtOrchestrator(
            execution_mode=ExecutionMode.PER_NODE,
            retries=2,
            concurrency=4,
        )
        return orchestrator.run_build()
    ```
    """

    def __init__(
        self,
        settings: PrefectDbtSettings | None = None,
        manifest_path: Path | None = None,
        executor: DbtExecutor | None = None,
        threads: int | None = None,
        state_path: Path | None = None,
        defer: bool = False,
        defer_state_path: Path | None = None,
        favor_state: bool = False,
        execution_mode: ExecutionMode = ExecutionMode.PER_WAVE,
        retries: int = 0,
        retry_delay_seconds: int = 30,
        concurrency: str | int | None = None,
        task_runner_type: type | None = None,
        cache: CacheConfig | None = None,
        test_strategy: TestStrategy = TestStrategy.IMMEDIATE,
        create_summary_artifact: bool = True,
        include_compiled_code: bool = False,
        write_run_results: bool = False,
        disable_assets: bool = False,
        hooks: dict[str, list[Any]] | None = None,
    ):
        self._settings = (settings or PrefectDbtSettings()).model_copy()
        self._manifest_path = manifest_path
        try:
            self._execution_mode = ExecutionMode(execution_mode)
        except ValueError:
            raise ValueError(
                f"Invalid execution_mode {execution_mode!r}. "
                f"Must be one of: {', '.join(m.value for m in ExecutionMode)}"
            ) from None
        try:
            self._test_strategy = TestStrategy(test_strategy)
        except ValueError:
            raise ValueError(
                f"Invalid test_strategy {test_strategy!r}. "
                f"Must be one of: {', '.join(s.value for s in TestStrategy)}"
            ) from None
        self._retries = retries
        self._retry_delay_seconds = retry_delay_seconds
        self._concurrency = concurrency
        self._task_runner_type = task_runner_type
        self._cache = cache
        self._create_summary_artifact = create_summary_artifact
        self._include_compiled_code = include_compiled_code
        self._write_run_results = write_run_results
        self._disable_assets = disable_assets
        self.hooks = hooks or {}

        if retries and self._execution_mode != ExecutionMode.PER_NODE:
            raise ValueError(
                "Retries are only supported in PER_NODE execution mode. "
                "Set execution_mode=ExecutionMode.PER_NODE to use retries."
            )

        if cache is not None and self._execution_mode != ExecutionMode.PER_NODE:
            raise ValueError(
                "Caching is only supported in PER_NODE execution mode. "
                "Set execution_mode=ExecutionMode.PER_NODE to use caching."
            )

        # When the caller provides an explicit manifest_path that lives
        # outside the default target dir, align settings.target_path so
        # that both resolve_selection() and the executor use the same
        # target directory.  Without this, selection and execution could
        # resolve against different target dirs.
        if manifest_path is not None:
            self._settings.target_path = self._resolve_target_path()

        if executor is not None:
            self._executor = executor
        else:
            self._executor = DbtCoreExecutor(
                self._settings,
                threads=threads,
                state_path=state_path,
                defer=defer,
                defer_state_path=defer_state_path,
                favor_state=favor_state,
            )

    def _run_hooks(self, hook_name: str, **payload: Any) -> None:
        """Run configured lifecycle hooks without interrupting orchestration."""
        for hook in self.hooks.get(hook_name, []):
            try:
                hook(**payload)
            except Exception as exc:
                logger.warning(
                    "Error in PrefectDbtOrchestrator hook '%s': %s", hook_name, exc
                )

    @staticmethod
    def _build_node_result(
        status: str,
        timing: dict[str, Any] | None = None,
        invocation: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        reason: str | None = None,
        failed_upstream: list[str] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"status": status}
        if timing is not None:
            result["timing"] = timing
        if invocation is not None:
            result["invocation"] = invocation
        if error is not None:
            result["error"] = error
        if reason is not None:
            result["reason"] = reason
        if failed_upstream is not None:
            result["failed_upstream"] = failed_upstream
        return result

    def _create_artifacts(
        self,
        results: dict[str, Any],
        elapsed_time: float,
    ) -> None:
        """Create post-execution artifacts (summary markdown, run_results.json)."""
        if self._create_summary_artifact:
            if FlowRunContext.get() is not None:
                try:
                    markdown = create_summary_markdown(results)
                    create_markdown_artifact(
                        markdown=markdown,
                        key="dbt-orchestrator-summary",
                        _sync=True,
                    )
                except Exception as e:
                    logger.warning("Failed to create dbt summary artifact: %s", e)
                else:
                    logger.info(
                        "Summary artifact created: key='dbt-orchestrator-summary'"
                    )

        if self._write_run_results:
            target_dir = self._settings.project_dir / self._settings.target_path
            out_path = write_run_results_json(results, elapsed_time, target_dir)
            logger.info("run_results.json written to %s", out_path)

    def _resolve_target_path(self) -> Path:
        """Resolve the target directory path.

        When `manifest_path` is explicitly set, normalizes it to an absolute
        path (relative to `settings.project_dir`) and returns its parent
        directory so that `resolve_selection` uses the same target directory
        as the manifest. Otherwise, returns `settings.target_path`.
        """
        if self._manifest_path is not None:
            if self._manifest_path.is_absolute():
                return self._manifest_path.parent
            return (self._settings.project_dir / self._manifest_path).resolve().parent
        return self._settings.target_path

    def _resolve_manifest_path(self) -> Path:
        """Resolve the path to manifest.json.

        Resolution order:

        1. Explicit `manifest_path` (relative paths resolved against
           `settings.project_dir`).  If the file does not exist, returns
           the path as-is — `ManifestParser` will raise a clear error.
        2. Delegates to the executor's `resolve_manifest_path()`.  The
           executor is responsible for locating or generating the manifest
           (e.g. running `dbt parse` locally or fetching from dbt Cloud).

        Returns:
            Resolved `Path` to the `manifest.json` file.
        """
        if self._manifest_path is not None:
            if self._manifest_path.is_absolute():
                return self._manifest_path
            return (self._settings.project_dir / self._manifest_path).resolve()

        path = self._executor.resolve_manifest_path()
        self._manifest_path = path
        self._settings.target_path = path.parent
        return path

    @staticmethod
    def _augment_immediate_test_edges(
        merged_nodes: dict[str, DbtNode],
        test_nodes: dict[str, DbtNode],
    ) -> dict[str, DbtNode]:
        """Add implicit edges so downstream models depend on upstream tests.

        Under `dbt build`, a test failure on model M causes all downstream
        models of M to be skipped.  In the orchestrator's DAG, both the
        test on M and a downstream model D originally share the same
        dependency (M), placing them in the same wave.  That means the
        test cannot block D.

        This method adds an implicit dependency: for every test T that
        depends on model M, every non-test node D whose `depends_on`
        includes M also gains a dependency on T.  Kahn's algorithm then
        places T in an earlier wave than D, allowing test-failure
        cascading to work correctly in both PER_WAVE and PER_NODE modes.

        Args:
            merged_nodes: Combined dict of model + test nodes.
            test_nodes: Subset containing only test nodes.

        Returns:
            A new dict of nodes with augmented dependencies.  Only nodes
            whose `depends_on` changed are replaced; all others are the
            original objects.
        """
        # Build a mapping: model_id -> list of test unique_ids that test it.
        model_to_tests: dict[str, list[str]] = {}
        for test_id, test_node in test_nodes.items():
            for parent_id in test_node.depends_on:
                model_to_tests.setdefault(parent_id, []).append(test_id)

        if not model_to_tests:
            return merged_nodes

        # Build a reverse adjacency (parent -> children) for descendant
        # lookups used by the cycle guard below.
        children_of: dict[str, list[str]] = {}
        for nid, node_ in merged_nodes.items():
            for dep_id in node_.depends_on:
                children_of.setdefault(dep_id, []).append(nid)

        def _descendants(start: str) -> set[str]:
            """Return all transitive descendants of `start`."""
            visited: set[str] = set()
            stack = list(children_of.get(start, ()))
            while stack:
                nid = stack.pop()
                if nid in visited:
                    continue
                visited.add(nid)
                stack.extend(children_of.get(nid, ()))
            return visited

        # For each non-test node, check if any of its dependencies have
        # tests.  If so, add those test IDs as extra dependencies.
        #
        # Cycle guard: adding D → T (D depends on test T) would create a
        # cycle if T transitively reaches D through its other parents.
        # This happens when a multi-parent test (e.g. a relationship test)
        # depends on a model that is a descendant of D.  We detect this by
        # checking whether *any* parent of T is D itself or a descendant
        # of D in the original graph.
        result = dict(merged_nodes)
        descendants_cache: dict[str, set[str]] = {}
        for node_id, node in merged_nodes.items():
            if node_id in test_nodes:
                continue
            extra_deps: list[str] = []
            for dep_id in node.depends_on:
                if dep_id in model_to_tests:
                    for tid in model_to_tests[dep_id]:
                        # Check if any of the test's parents is node_id
                        # itself or a transitive descendant of node_id.
                        if node_id not in descendants_cache:
                            descendants_cache[node_id] = _descendants(node_id)
                        test_parents = set(test_nodes[tid].depends_on)
                        if not test_parents & (descendants_cache[node_id] | {node_id}):
                            extra_deps.append(tid)
            if extra_deps:
                new_depends_on = node.depends_on + tuple(dict.fromkeys(extra_deps))
                result[node_id] = dataclasses.replace(node, depends_on=new_depends_on)
        return result

    def _prepare_build(
        self,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
        only_fresh_sources: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
        *,
        _resolved_profiles_dir: str | None = None,
    ) -> tuple[
        list[ExecutionWave],
        list[dict[str, DbtNode]],
        dict[str, DbtNode],
        dict[str, Any],
        dict,
        ManifestParser,
    ]:
        """Execute steps 1-6 of the build pipeline without running anything.

        Shared by `run_build` and `plan`.

        Args:
            _resolved_profiles_dir: When provided by the caller (e.g.
                `run_build`), reuse this already-resolved profiles
                directory instead of opening a new temporary context.
                This avoids duplicate Prefect API calls for block /
                variable resolution.

        Returns:
            A tuple of `(waves, phases, filtered_nodes, skipped_results,
            freshness_results, parser)`.  `phases` is a list of
            node-dicts for eager per-node scheduling.
        """
        # 1. Parse manifest
        manifest_path = self._resolve_manifest_path()
        parser = ManifestParser(manifest_path)

        # 2. Resolve selectors if provided
        selected_ids: set[str] | None = None
        if select is not None or exclude is not None:
            if _resolved_profiles_dir is not None:
                # Caller already resolved profiles — reuse directly.
                selected_ids = resolve_selection(
                    project_dir=self._settings.project_dir,
                    profiles_dir=Path(_resolved_profiles_dir),
                    select=select,
                    exclude=exclude,
                    target_path=self._resolve_target_path(),
                    target=target,
                )
            else:
                # Standalone call (e.g. from plan()) — resolve in a
                # local context that is cleaned up immediately.
                with self._settings.resolve_profiles_yml() as rpd:
                    if isinstance(self._executor, DbtCoreExecutor):
                        with self._executor.use_resolved_profiles_dir(rpd):
                            selected_ids = resolve_selection(
                                project_dir=self._settings.project_dir,
                                profiles_dir=Path(rpd),
                                select=select,
                                exclude=exclude,
                                target_path=self._resolve_target_path(),
                                target=target,
                            )
                    else:
                        selected_ids = resolve_selection(
                            project_dir=self._settings.project_dir,
                            profiles_dir=Path(rpd),
                            select=select,
                            exclude=exclude,
                            target_path=self._resolve_target_path(),
                            target=target,
                        )

        # 3. Filter nodes
        filtered_nodes = parser.filter_nodes(selected_node_ids=selected_ids)

        # 4. Source freshness integration
        freshness_results: dict = {}
        skipped_results: dict[str, Any] = {}

        if only_fresh_sources or (
            self._cache is not None and self._cache.use_source_freshness_expiration
        ):
            freshness_results = run_source_freshness(
                self._settings,
                target_path=self._resolve_target_path(),
                target=target,
            )

            if only_fresh_sources and freshness_results:
                filtered_nodes, skipped_results = filter_stale_nodes(
                    filtered_nodes, parser.all_nodes, freshness_results
                )

        # 5. Collect test nodes when strategy != SKIP
        test_nodes: dict = {}
        if self._test_strategy != TestStrategy.SKIP:
            test_nodes = parser.filter_test_nodes(
                selected_node_ids=selected_ids,
                executable_node_ids=set(filtered_nodes.keys()),
            )

        # 6. Compute waves from remaining nodes
        if self._test_strategy == TestStrategy.IMMEDIATE and test_nodes:
            merged = {**filtered_nodes, **test_nodes}
            augmented = self._augment_immediate_test_edges(merged, test_nodes)
            waves = parser.compute_execution_waves(nodes=augmented)
            phases: list[dict[str, DbtNode]] = [augmented]
        elif self._test_strategy == TestStrategy.DEFERRED and test_nodes:
            model_waves = parser.compute_execution_waves(nodes=filtered_nodes)
            test_waves = parser.compute_execution_waves(nodes=test_nodes)
            next_wave_num = (model_waves[-1].wave_number + 1) if model_waves else 0
            for tw in test_waves:
                tw.wave_number = next_wave_num
                next_wave_num += 1
            waves = model_waves + test_waves
            phases = [filtered_nodes, test_nodes]
        else:
            waves = parser.compute_execution_waves(nodes=filtered_nodes)
            phases = [filtered_nodes]

        return waves, phases, filtered_nodes, skipped_results, freshness_results, parser

    def plan(
        self,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
        only_fresh_sources: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> BuildPlan:
        """Dry-run: preview what `run_build` would execute.

        Performs steps 1-6 of the build pipeline (manifest parse, selector
        resolution, node filtering, source freshness, test scheduling,
        wave computation) **without** executing any dbt commands beyond
        `dbt ls` (for selector resolution) and `dbt source freshness`
        (when `only_fresh_sources` or freshness-based cache expiration
        is enabled).

        Args:
            select: dbt selector expression (e.g. `"tag:daily"`)
            exclude: dbt exclude expression
            full_refresh: Whether `--full-refresh` would be passed
            only_fresh_sources: When True, filter out models with stale
                upstream sources
            target: dbt target name override
            extra_cli_args: Additional dbt CLI flags (validated the same
                way as in `run_build`)

        Returns:
            A `BuildPlan` describing the waves, node count, cache
            predictions, skipped nodes, and estimated parallelism.
        """
        waves, _phases, filtered_nodes, skipped_results, freshness_results, parser = (
            self._prepare_build(
                select=select,
                exclude=exclude,
                full_refresh=full_refresh,
                only_fresh_sources=only_fresh_sources,
                target=target,
                extra_cli_args=extra_cli_args,
            )
        )

        node_count = sum(len(w.nodes) for w in waves)
        estimated_parallelism = max((len(w.nodes) for w in waves), default=0)

        # Cache predictions
        cache_predictions: dict[str, str] | None = None
        if self._cache is not None:
            cache_predictions = {}
            macro_paths = parser.get_macro_paths()
            all_executable_nodes = parser.get_executable_nodes()
            precomputed = self._precompute_all_cache_keys(
                all_executable_nodes, full_refresh, macro_paths
            )
            execution_state = self._load_execution_state()

            for wave in waves:
                for node in wave.nodes:
                    nid = node.unique_id
                    if (
                        node.resource_type in self._cache.exclude_resource_types
                        or node.materialization in self._cache.exclude_materializations
                    ):
                        cache_predictions[nid] = "excluded"
                    elif full_refresh:
                        cache_predictions[nid] = "miss"
                    elif nid in precomputed and precomputed[nid] == execution_state.get(
                        nid
                    ):
                        cache_predictions[nid] = "hit"
                    else:
                        cache_predictions[nid] = "miss"

        return BuildPlan(
            waves=tuple(waves),
            node_count=node_count,
            cache_predictions=cache_predictions,
            skipped_nodes=skipped_results,
            estimated_parallelism=estimated_parallelism,
        )

    def run_build(
        self,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
        only_fresh_sources: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a dbt build wave-by-wave or per-node.

        Pipeline:
        1. Parse the manifest
        2. Optionally resolve selectors to filter nodes
        3. Filter nodes
        4. Optionally run source freshness and filter stale nodes
        5. Compute execution waves (topological order)
        6. Execute (per-wave or per-node depending on mode)

        In **PER_NODE** mode, each node becomes a separate Prefect task with
        individual retries.  This requires `run_build()` to be called
        inside a `@flow`.

        Args:
            select: dbt selector expression (e.g. `"tag:daily"`)
            exclude: dbt exclude expression
            full_refresh: Whether to pass `--full-refresh` to dbt
            only_fresh_sources: When True, skip models whose upstream
                sources are stale (freshness status "error" or "runtime
                error").  Downstream dependents are also skipped.
            target: dbt target name to override the default from
                profiles.yml (maps to `--target` / `-t`)
            extra_cli_args: Additional dbt CLI flags to pass through
                to every dbt invocation.  Useful for flags the
                orchestrator does not expose as first-class parameters
                (e.g. `["--store-failures", "--vars",
                "{'my_var': 'value'}"]`).  Flags that conflict with
                orchestrator-managed settings are rejected with a
                `ValueError`.

        Returns:
            Dict mapping node unique_id to result dict. Each result has:
            - `status`: `"success"`, `"cached"`, `"error"`, or `"skipped"`
            - `timing`: `{started_at, completed_at, duration_seconds}`
              (not present for skipped nodes)
            - `invocation`: `{command, args}` (not present for skipped)
            - `error`: `{message, type}` (only for error status)
            - `reason`: reason string (only for skipped status)
            - `failed_upstream`: list of failed node IDs (only for skipped)

        Raises:
            ValueError: If `extra_cli_args` contains a blocked flag or
                a flag that has a first-class parameter equivalent.
        """
        raw_extra_cli_args = extra_cli_args
        extra_cli_args = list(extra_cli_args or [])
        _validate_extra_cli_args(extra_cli_args)

        self._run_hooks(
            "before_orchestration",
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
            only_fresh_sources=only_fresh_sources,
            target=target,
            extra_cli_args=extra_cli_args.copy(),
            orchestrator=self,
        )
        try:
            with ExitStack() as stack:
                resolved_profiles_dir: str | None = None

                def _ensure_resolved_profiles_dir() -> str:
                    """Resolve profiles lazily and pin them to the executor."""
                    nonlocal resolved_profiles_dir
                    if resolved_profiles_dir is None:
                        resolved_profiles_dir = stack.enter_context(
                            self._settings.resolve_profiles_yml()
                        )
                        if isinstance(self._executor, DbtCoreExecutor):
                            stack.enter_context(
                                self._executor.use_resolved_profiles_dir(
                                    resolved_profiles_dir
                                )
                            )
                    return resolved_profiles_dir

                # Eagerly resolve profiles when selectors will need them so
                # the same temp dir is reused for execution later.
                if select is not None or exclude is not None:
                    _ensure_resolved_profiles_dir()
                    self._run_hooks(
                        "before_selector",
                        select=select,
                        exclude=exclude,
                        target=target,
                        extra_cli_args=extra_cli_args.copy(),
                        orchestrator=self,
                    )

                (
                    waves,
                    phases,
                    filtered_nodes,
                    skipped_results,
                    freshness_results,
                    parser,
                ) = self._prepare_build(
                    select=select,
                    exclude=exclude,
                    full_refresh=full_refresh,
                    only_fresh_sources=only_fresh_sources,
                    target=target,
                    extra_cli_args=raw_extra_cli_args,
                    _resolved_profiles_dir=resolved_profiles_dir,
                )

                if select is not None or exclude is not None:
                    self._run_hooks(
                        "after_selector",
                        select=select,
                        exclude=exclude,
                        filtered_nodes=filtered_nodes,
                        waves=waves,
                        phases=phases,
                        orchestrator=self,
                    )

                # 7. Execute
                build_started = datetime.now(timezone.utc)

                # Ensure profiles are resolved for execution modes that
                # invoke dbt directly.
                if isinstance(self._executor, DbtCoreExecutor) and (
                    self._execution_mode == ExecutionMode.PER_WAVE
                    or self._cache is None
                ):
                    _ensure_resolved_profiles_dir()

                execution_results = self._run_execution(
                    waves,
                    phases,
                    full_refresh,
                    freshness_results,
                    parser,
                    target=target,
                    extra_cli_args=raw_extra_cli_args,
                )

                build_completed = datetime.now(timezone.utc)
                elapsed_time = (build_completed - build_started).total_seconds()

                # Merge skipped results with execution results
                if skipped_results:
                    execution_results.update(skipped_results)

                # 8. Post-execution: artifacts
                self._create_artifacts(execution_results, elapsed_time)
                self._run_hooks(
                    "after_orchestration",
                    result=execution_results,
                    elapsed_time=elapsed_time,
                    select=select,
                    exclude=exclude,
                    full_refresh=full_refresh,
                    target=target,
                    orchestrator=self,
                )

                return execution_results
        except Exception as exc:
            self._run_hooks(
                "on_orchestration_failure",
                error=exc,
                select=select,
                exclude=exclude,
                full_refresh=full_refresh,
                target=target,
                orchestrator=self,
            )
            raise

    def _run_execution(
        self,
        waves: list[ExecutionWave],
        phases: list[dict[str, DbtNode]],
        full_refresh: bool,
        freshness_results: dict,
        parser: ManifestParser,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Dispatch execution to the appropriate mode handler."""
        if self._execution_mode == ExecutionMode.PER_NODE:
            macro_paths = parser.get_macro_paths() if self._cache is not None else {}
            largest_wave = max((len(w.nodes) for w in waves), default=1)
            return self._execute_per_node(
                waves,
                phases,
                largest_wave,
                full_refresh,
                macro_paths,
                freshness_results=freshness_results
                if self._cache is not None
                and self._cache.use_source_freshness_expiration
                else None,
                all_nodes=parser.all_nodes,
                adapter_type=parser.adapter_type,
                project_name=parser.project_name,
                target=target,
                extra_cli_args=extra_cli_args,
                all_executable_nodes=parser.get_executable_nodes(),
            )
        else:
            return self._execute_per_wave(
                waves,
                full_refresh,
                target=target,
                extra_cli_args=extra_cli_args,
            )

    # ------------------------------------------------------------------
    # PER_WAVE execution
    # ------------------------------------------------------------------

    def _execute_per_wave(
        self,
        waves,
        full_refresh,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ):
        """Execute waves one at a time, each as a single dbt invocation."""
        results: dict[str, Any] = {}
        failed_nodes: list[str] = []

        # Always suppress dbt's automatic indirect test selection in
        # PER_WAVE mode.  The orchestrator owns test scheduling:
        #   SKIP     → no tests at all (indirect selection would leak them)
        #   IMMEDIATE/DEFERRED → tests only in orchestrator-placed waves
        indirect_selection = "empty"

        try:
            run_logger = get_run_logger()
        except Exception:
            run_logger = logger

        for wave in waves:
            if failed_nodes:
                # Skip this wave -- upstream failure
                for node in wave.nodes:
                    results[node.unique_id] = self._build_node_result(
                        status="skipped",
                        reason="upstream failure",
                        failed_upstream=list(failed_nodes),
                    )
                continue

            # Execute the wave
            started_at = datetime.now(timezone.utc)
            self._run_hooks(
                "before_wave",
                wave=wave,
                wave_nodes=wave.nodes,
                orchestrator=self,
            )
            try:
                wave_result: ExecutionResult = self._executor.execute_wave(
                    wave.nodes,
                    full_refresh=full_refresh,
                    indirect_selection=indirect_selection,
                    target=target,
                    extra_cli_args=extra_cli_args,
                )
            except Exception as exc:
                wave_result = ExecutionResult(
                    success=False,
                    node_ids=[n.unique_id for n in wave.nodes],
                    error=exc,
                )
            completed_at = datetime.now(timezone.utc)
            self._run_hooks(
                "after_wave",
                wave=wave,
                wave_nodes=wave.nodes,
                result=wave_result,
                success=wave_result.success,
                orchestrator=self,
            )

            for node in wave.nodes:
                _emit_log_messages(wave_result.log_messages, node.unique_id, run_logger)
            _emit_log_messages(wave_result.log_messages, "", run_logger)

            timing = {
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": (completed_at - started_at).total_seconds(),
            }

            invocation = {
                "command": "build",
                "args": [n.unique_id for n in wave.nodes],
            }

            if wave_result.success:
                for node in wave.nodes:
                    node_result = self._build_node_result(
                        status="success",
                        timing=dict(timing),
                        invocation=dict(invocation),
                    )
                    # Enrich with per-node execution_time from artifacts
                    if (
                        wave_result.artifacts
                        and node.unique_id in wave_result.artifacts
                    ):
                        artifact = wave_result.artifacts[node.unique_id]
                        if "execution_time" in artifact:
                            node_result["timing"]["execution_time"] = artifact[
                                "execution_time"
                            ]
                    results[node.unique_id] = node_result
            else:
                # PER_WAVE failure: use per-node artifact status when
                # available so that test failures don't incorrectly
                # cascade to sibling models or downstream waves.
                for node in wave.nodes:
                    # Check per-node artifact status to distinguish
                    # individually successful nodes from truly failed ones.
                    node_artifact = (
                        wave_result.artifacts.get(node.unique_id)
                        if wave_result.artifacts
                        else None
                    )
                    node_succeeded = node_artifact is not None and node_artifact.get(
                        "status"
                    ) in ("success", "pass")

                    if node_succeeded:
                        node_result = self._build_node_result(
                            status="success",
                            timing=dict(timing),
                            invocation=dict(invocation),
                        )
                        if "execution_time" in node_artifact:
                            node_result["timing"]["execution_time"] = node_artifact[
                                "execution_time"
                            ]
                        results[node.unique_id] = node_result
                    else:
                        # Prefer per-node artifact message (the real dbt
                        # error) over the wave-level exception which may
                        # be None when dbt records failures as node
                        # results rather than Python exceptions.
                        artifact_msg = (
                            node_artifact.get("message") if node_artifact else None
                        ) or None
                        error_info = {
                            "message": artifact_msg
                            or (
                                str(wave_result.error)
                                if wave_result.error
                                else "unknown error"
                            ),
                            "type": type(wave_result.error).__name__
                            if wave_result.error
                            else "UnknownError",
                        }
                        results[node.unique_id] = self._build_node_result(
                            status="error",
                            timing=dict(timing),
                            invocation=dict(invocation),
                            error=error_info,
                        )
                        # Propagate failures to downstream waves.
                        # Under IMMEDIATE, test failures also cascade
                        # to match `dbt build` semantics.
                        if (
                            node.resource_type not in _TEST_NODE_TYPES
                            or self._test_strategy == TestStrategy.IMMEDIATE
                        ):
                            failed_nodes.append(node.unique_id)

        return results

    # ------------------------------------------------------------------
    # PER_NODE execution
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Execution state — persistent record of each node's precomputed
    # cache key at the time it was last successfully executed.  Used to
    # decide whether an unexecuted upstream's warehouse data matches
    # the current file state (see _build_cache_options_for_node).
    # ------------------------------------------------------------------

    _EXECUTION_STATE_KEY = ".execution_state.json"

    @staticmethod
    def _resolve_maybe_coro(result):
        """Resolve a value that may be a coroutine (async impl) or plain value (sync impl)."""
        import inspect

        if inspect.isawaitable(result):
            from prefect.utilities.asyncutils import run_coro_as_sync

            return run_coro_as_sync(result)
        return result

    @staticmethod
    def _is_block_slug(value: str) -> bool:
        """Return True if *value* looks like a block slug (e.g. `type/name`)."""
        return len(value.split("/")) == 2

    def _resolve_storage(self) -> tuple[Path | None, Any]:
        """Resolve `CacheConfig.key_storage` into a local path or filesystem block.

        Returns `(path, None)` for local paths and `(None, block)` for
        `WritableFileSystem` instances or block-slug strings.  Returns
        `(None, None)` when caching is disabled or both key storage and
        result storage are unconfigured.

        When `key_storage` is `None` we fall back to
        `result_storage` because Prefect co-locates cache metadata with
        results by default, so execution state should live there too.
        """
        ks = self._cache.key_storage if self._cache else None
        if ks is None and self._cache is not None:
            # Fall back to result_storage — cache keys are co-located with
            # results by default, so execution state should be too.
            ks = self._cache.result_storage
        if ks is None:
            return None, None
        if isinstance(ks, Path):
            return ks, None
        if isinstance(ks, str):
            if self._is_block_slug(ks):
                from prefect.results import resolve_result_storage

                block = resolve_result_storage(ks, _sync=True)
                return None, block
            return Path(ks), None
        # WritableFileSystem instance
        return None, ks

    def _load_execution_state(self) -> dict[str, str]:
        """Load `{node_id: cache_key}` from persisted execution state."""
        try:
            path, block = self._resolve_storage()
            if path is not None:
                return _json.loads((path / self._EXECUTION_STATE_KEY).read_text())
            if block is not None:
                data = self._resolve_maybe_coro(
                    block.read_path(self._EXECUTION_STATE_KEY)
                )
                return _json.loads(data)
        except Exception:
            pass
        return {}

    def _save_execution_state(self, state: dict[str, str]) -> None:
        """Persist the execution state dict."""
        content = _json.dumps(state).encode()
        try:
            path, block = self._resolve_storage()
            if path is not None:
                (path / self._EXECUTION_STATE_KEY).write_bytes(content)
            elif block is not None:
                self._resolve_maybe_coro(
                    block.write_path(self._EXECUTION_STATE_KEY, content)
                )
        except Exception as exc:
            logger.debug("Could not save execution state: %s", exc)

    def _build_cache_options_for_node(
        self,
        node,
        full_refresh,
        computed_cache_keys,
        macro_paths=None,
        freshness_results=None,
        all_nodes=None,
        precomputed_cache_keys=None,
        execution_state=None,
    ):
        """Build cache-related `with_options` kwargs and record the eager key.

        Returns a dict of extra kwargs to merge into `with_options`.
        As a side-effect, stores the pre-computed cache key in
        *computed_cache_keys* so downstream nodes can incorporate it.

        When *precomputed_cache_keys* is provided, upstream dependencies
        that were not executed in this run (absent from
        *computed_cache_keys*) can still be resolved from the
        pre-computed dict.

        *execution_state* maps each node to the precomputed key it had
        when last successfully executed.  When an upstream's persisted
        state matches its current precomputed key the warehouse is
        assumed current and the upstream key is used unsalted (same
        cache namespace as a full build).  Otherwise the key is salted
        with `":unexecuted"` so independent upstream rebuilds
        invalidate the downstream cache entry.
        """
        precomputed = precomputed_cache_keys or {}
        state = execution_state or {}
        upstream_keys = {}
        for dep_id in node.depends_on:
            if dep_id in computed_cache_keys:
                upstream_keys[dep_id] = computed_cache_keys[dep_id]
            elif dep_id in precomputed:
                if state.get(dep_id) == precomputed[dep_id]:
                    # Upstream was previously executed with the same
                    # file state it has now — warehouse data should be
                    # current.  Use the unsalted key so this selective
                    # run shares the full-build cache namespace.
                    upstream_keys[dep_id] = precomputed[dep_id]
                else:
                    # Upstream was never executed with the current file
                    # state.  Salt the key so the cache entry is
                    # distinct and will be invalidated when upstream is
                    # eventually rebuilt.
                    upstream_keys[dep_id] = precomputed[dep_id] + ":unexecuted"
            else:
                # An upstream dependency has no cache key (e.g. its
                # source file is missing from disk).  We cannot
                # guarantee the cached result is still valid so
                # disable caching for this node.
                logger.debug(
                    "Disabling cache for %s: upstream %s has no cache key",
                    node.unique_id,
                    dep_id,
                )
                return {}
        policy = build_cache_policy_for_node(
            node,
            self._settings.project_dir,
            full_refresh,
            upstream_keys,
            self._cache.key_storage if self._cache else None,
            macro_paths=macro_paths,
        )
        key = policy.compute_key(None, {}, {})
        if key is not None:
            computed_cache_keys[node.unique_id] = key

        opts: dict[str, Any] = {
            "cache_policy": policy,
            "persist_result": True,
        }
        if full_refresh:
            opts["refresh_cache"] = True

        # Determine cache_expiration: freshness-based or default
        cache_expiration = self._cache.expiration if self._cache else None
        if (
            self._cache is not None
            and self._cache.use_source_freshness_expiration
            and freshness_results
            and all_nodes
        ):
            freshness_exp = compute_freshness_expiration(
                node.unique_id, all_nodes, freshness_results
            )
            if freshness_exp is not None:
                cache_expiration = freshness_exp

        if cache_expiration is not None:
            opts["cache_expiration"] = cache_expiration
        if self._cache is not None and self._cache.result_storage is not None:
            opts["result_storage"] = self._cache.result_storage
        return opts

    def _precompute_all_cache_keys(
        self,
        all_executable_nodes: dict[str, DbtNode],
        full_refresh: bool,
        macro_paths: dict[str, str | None],
    ) -> dict[str, str]:
        """Pre-compute cache keys for all executable nodes in topological order.

        Walks *all_executable_nodes* using Kahn's algorithm so that each
        node's upstream keys are available before its own key is computed.
        This ensures nodes whose upstream dependencies are outside the
        current `select=` filter still get valid cache keys, since cache
        keys are pure functions of manifest metadata and file contents —
        they don't require execution.

        Returns:
            Mapping of `node.unique_id` to its computed cache key string.
            Nodes whose key could not be computed (e.g. missing file on
            disk) are omitted from the dict.
        """
        computed: dict[str, str] = {}
        nodes = all_executable_nodes

        # Build in-degree map scoped to *nodes* (same logic as
        # ManifestParser.compute_execution_waves).
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {nid: [] for nid in nodes}
        for nid, node in nodes.items():
            deps_in_graph = [d for d in node.depends_on if d in nodes]
            in_degree[nid] = len(deps_in_graph)
            for dep_id in deps_in_graph:
                dependents[dep_id].append(nid)

        current_wave = [nid for nid, deg in in_degree.items() if deg == 0]

        while current_wave:
            next_wave: list[str] = []
            for nid in current_wave:
                node = nodes[nid]
                # Gather upstream keys (only those within all_executable_nodes)
                upstream_keys: dict[str, str] = {}
                skip = False
                for dep_id in node.depends_on:
                    if dep_id in computed:
                        upstream_keys[dep_id] = computed[dep_id]
                    elif dep_id in nodes:
                        # Dependency is in the graph but has no key (its
                        # own computation failed).  Skip this node.
                        skip = True
                        break
                    # else: dependency is outside executable nodes (e.g.
                    # a source) — not an error, just not in upstream_keys.

                if not skip:
                    # Guard: if the node declares a source file but we
                    # cannot read it, the resulting key would not track
                    # file-content changes.  Refuse to record a key so
                    # that downstream nodes fall back to uncached
                    # execution (same as the pre-fix behaviour).
                    if node.original_file_path:
                        file_path = self._settings.project_dir / node.original_file_path
                        try:
                            file_path.read_bytes()
                        except (OSError, IOError):
                            logger.debug(
                                "Skipping cache key for %s: source file "
                                "unreadable at %s",
                                nid,
                                file_path,
                            )
                            for dependent_id in dependents[nid]:
                                in_degree[dependent_id] -= 1
                                if in_degree[dependent_id] == 0:
                                    next_wave.append(dependent_id)
                            continue

                    policy = build_cache_policy_for_node(
                        node,
                        self._settings.project_dir,
                        full_refresh,
                        upstream_keys,
                        macro_paths=macro_paths,
                    )
                    key = policy.compute_key(None, {}, {})
                    if key is not None:
                        computed[nid] = key

                for dependent_id in dependents[nid]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_wave.append(dependent_id)

            current_wave = next_wave

        return computed

    def _execute_per_node(
        self,
        waves,
        phases,
        largest_wave,
        full_refresh,
        macro_paths=None,
        freshness_results=None,
        all_nodes=None,
        adapter_type=None,
        project_name=None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
        all_executable_nodes=None,
    ):
        """Execute each node as an individual Prefect task.

        Creates a separate Prefect task per node with individual retries.
        Nodes are submitted eagerly as soon as all their individual
        dependencies complete, maximizing concurrency without artificial
        wave barriers.  Failed nodes cause their downstream dependents
        to be skipped.

        For models, seeds, and snapshots with a `relation_name`, the
        task is wrapped in a `MaterializingTask` that tracks asset
        lineage in Prefect's asset graph.

        Each subprocess gets its own dbt adapter registry (`FACTORY`
        singleton), so there is no shared mutable state.  Adapter
        pooling is enabled so connections survive across invocations
        within the same worker process.

        Requires an active Prefect flow run context (call inside a `@flow`).
        """
        if self._task_runner_type is None:
            task_runner_type = ProcessPoolTaskRunner
        else:
            task_runner_type = self._task_runner_type

        executor = self._executor
        if issubclass(task_runner_type, ProcessPoolTaskRunner) and isinstance(
            executor, DbtCoreExecutor
        ):
            executor._pool_adapters = True
        concurrency_name = (
            self._concurrency if isinstance(self._concurrency, str) else None
        )
        build_result = self._build_node_result
        all_nodes_map = all_nodes or {}

        # Compute max_workers for the task runner. For ProcessPool-based
        # execution, cap worker count to 2× local CPUs — dbt nodes are
        # mostly I/O-bound (waiting on the database), so moderate
        # oversubscription improves throughput without excessive overhead.
        max_workers = self._determine_per_node_max_workers(
            task_runner_type=task_runner_type,
            largest_wave=largest_wave,
        )
        task_runner = task_runner_type(max_workers=max_workers)
        is_process_pool_task_runner = isinstance(task_runner, ProcessPoolTaskRunner)
        if is_process_pool_task_runner:
            try:
                existing_processor_factories = tuple(
                    task_runner.subprocess_message_processor_factories or ()
                )
            except (AttributeError, TypeError):
                existing_processor_factories = ()
            processor_factories = existing_processor_factories
            if _dbt_global_log_dedupe_processor_factory not in processor_factories:
                processor_factories = (
                    *processor_factories,
                    _dbt_global_log_dedupe_processor_factory,
                )
            if not _configure_process_pool_subprocess_message_processors(
                task_runner, list(processor_factories)
            ):
                logger.debug(
                    "Task runner %s does not support subprocess message processor "
                    "configuration; process-pool global-log dedupe injection disabled.",
                    type(task_runner).__name__,
                )

        # Unique token for this build invocation.  Every result dict
        # produced by `_run_dbt_node` carries this token under
        # `_build_run_id`.  On a cache hit Prefect returns the *stored*
        # result from a prior run whose token differs, so comparing the
        # token after `future.result()` reliably distinguishes fresh
        # executions from cache hits — even across process boundaries
        # (ProcessPoolTaskRunner).
        build_run_id = uuid4().hex
        if is_process_pool_task_runner:
            # Process-pool runs dedupe dbt global logs in the parent-process
            # message forwarder so task subprocesses can emit raw captured logs.
            def _emit_global_log_messages(task_logger, result) -> None:
                global_logger = task_logger.getChild("dbt_orchestrator_global")
                _emit_log_messages(result.log_messages, "", global_logger)

        else:
            # In-process task runners emit captured global dbt logs directly.
            def _emit_global_log_messages(task_logger, result) -> None:
                global_logger = task_logger.getChild("dbt_orchestrator_global")
                _emit_log_messages(result.log_messages, "", global_logger)

        # The core task function.  Shared by both regular Task and
        # MaterializingTask paths; the only difference is how the task
        # object wrapping this function is constructed.
        def _run_dbt_node(
            node,
            command,
            full_refresh,
            target=None,
            asset_key=None,
            extra_cli_args=None,
        ):
            # Acquire named concurrency slot if configured
            if concurrency_name:
                ctx = prefect_concurrency(concurrency_name, strict=True)
            else:
                ctx = nullcontext()

            started_at = datetime.now(timezone.utc)
            with ctx:
                result = executor.execute_node(
                    node,
                    command,
                    full_refresh,
                    target=target,
                    extra_cli_args=extra_cli_args,
                )
            completed_at = datetime.now(timezone.utc)

            try:
                task_logger = get_run_logger()
                _emit_log_messages(result.log_messages, node.unique_id, task_logger)
                _emit_global_log_messages(task_logger, result)
            except Exception:
                pass

            timing = {
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": (completed_at - started_at).total_seconds(),
            }
            invocation = {
                "command": command,
                "args": [node.unique_id],
            }

            if result.success:
                node_result = build_result(
                    status="success", timing=timing, invocation=invocation
                )
                if result.artifacts and node.unique_id in result.artifacts:
                    artifact = result.artifacts[node.unique_id]
                    if "execution_time" in artifact:
                        node_result["timing"]["execution_time"] = artifact[
                            "execution_time"
                        ]

                # Add asset metadata when running inside a MaterializingTask.
                if asset_key:
                    try:
                        asset_ctx = AssetContext.get()
                        if asset_ctx:
                            metadata: dict[str, Any] = {"status": "success"}
                            if result.artifacts and node.unique_id in result.artifacts:
                                metadata.update(result.artifacts[node.unique_id])
                            asset_ctx.add_asset_metadata(asset_key, metadata)
                    except Exception:
                        pass

                node_result["_build_run_id"] = build_run_id
                return node_result

            # Ensure the error is pickle-safe before raising across processes.
            # dbt exceptions may not be picklable, so convert to RuntimeError.
            if result.error:
                safe_error = RuntimeError(str(result.error))
                result = ExecutionResult(
                    success=result.success,
                    node_ids=result.node_ids,
                    error=safe_error,
                    artifacts=result.artifacts,
                )
            raise _DbtNodeError(result, timing, invocation)

        # Create a base task for non-asset nodes.
        base_task = prefect_task(_run_dbt_node)

        def _mark_failed(node_id):
            failed_nodes.add(node_id)
            computed_cache_keys.pop(node_id, None)

        def _build_asset_task(node, with_opts):
            """Create a MaterializingTask for nodes that produce assets."""
            if (
                adapter_type
                and node.resource_type in ASSET_NODE_TYPES
                and node.relation_name
            ):
                description_suffix = ""
                if self._include_compiled_code and project_name:
                    description_suffix = get_compiled_code_for_node(
                        node,
                        self._settings.project_dir,
                        self._settings.target_path,
                        project_name,
                    )

                asset = create_asset_for_node(node, adapter_type, description_suffix)
                upstream_assets = get_upstream_assets_for_node(
                    node, all_nodes_map, adapter_type
                )

                asset_key = format_resource_id(adapter_type, node.relation_name)
                return (
                    MaterializingTask(
                        fn=_run_dbt_node,
                        assets=[asset],
                        materialized_by="dbt",
                        asset_deps=upstream_assets or None,
                        **with_opts,
                    ),
                    asset_key,
                )

            return None, None

        results: dict[str, Any] = {}
        failed_nodes: set[str] = set()
        if self._cache is not None and all_executable_nodes:
            precomputed_cache_keys = self._precompute_all_cache_keys(
                all_executable_nodes,
                full_refresh,
                macro_paths or {},
            )
            execution_state = self._load_execution_state()
        else:
            precomputed_cache_keys: dict[str, str] = {}
            execution_state: dict[str, str] = {}
        computed_cache_keys: dict[str, str] = {}
        wave_number_by_node_id: dict[str, int] = {}
        wave_nodes_by_number: dict[int, list[DbtNode]] = {}
        emitted_before_waves: set[int] = set()
        emitted_after_waves: set[int] = set()

        if waves:
            for wave in waves:
                wave_nodes_by_number[wave.wave_number] = list(wave.nodes)
                for node in wave.nodes:
                    wave_number_by_node_id[node.unique_id] = wave.wave_number

        def _maybe_emit_before_wave(node_id: str) -> None:
            wave_number = wave_number_by_node_id.get(node_id)
            if wave_number is None or wave_number in emitted_before_waves:
                return

            emitted_before_waves.add(wave_number)
            self._run_hooks(
                "before_wave",
                wave=None,
                wave_number=wave_number,
                wave_nodes=wave_nodes_by_number.get(wave_number, []),
                orchestrator=self,
            )

        def _maybe_emit_after_wave(node_id: str) -> None:
            wave_number = wave_number_by_node_id.get(node_id)
            if wave_number is None or wave_number in emitted_after_waves:
                return

            wave_nodes = wave_nodes_by_number.get(wave_number, [])
            wave_node_ids = {node.unique_id for node in wave_nodes}
            if not wave_node_ids or not wave_node_ids.issubset(results):
                return

            emitted_after_waves.add(wave_number)
            wave_results = {wave_node_id: results[wave_node_id] for wave_node_id in wave_node_ids}
            wave_success = all(
                result.get("status") in {"success", "cached", "skipped"}
                for result in wave_results.values()
            )
            self._run_hooks(
                "after_wave",
                wave=None,
                wave_number=wave_number,
                wave_nodes=wave_nodes,
                result=wave_results,
                success=wave_success,
                orchestrator=self,
            )

        def _submit_node(node, runner):
            """Build task options, submit a node, and register the done callback."""
            command = _NODE_COMMAND.get(node.resource_type, "run")
            node_type_label = node.resource_type.value
            node_label = node.name if node.name else node.unique_id
            task_run_name = f"{node_type_label} {node_label}"
            _maybe_emit_before_wave(node.unique_id)
            self._run_hooks(
                "before_node_orchestration",
                node=node,
                command=command,
                orchestrator=self,
            )
            with_opts: dict[str, Any] = {
                "name": task_run_name,
                "task_run_name": task_run_name,
                "retries": self._retries,
                "retry_delay_seconds": self._retry_delay_seconds,
            }

            if (
                self._cache is not None
                and node.resource_type not in self._cache.exclude_resource_types
                and node.materialization not in self._cache.exclude_materializations
            ):
                with_opts.update(
                    self._build_cache_options_for_node(
                        node,
                        full_refresh,
                        computed_cache_keys,
                        macro_paths,
                        freshness_results=freshness_results,
                        all_nodes=all_nodes,
                        precomputed_cache_keys=precomputed_cache_keys,
                        execution_state=execution_state,
                    )
                )
            elif self._cache is not None:
                logger.debug(
                    "Skipping cache for %s: excluded by %s",
                    node.unique_id,
                    "resource_type"
                    if node.resource_type in self._cache.exclude_resource_types
                    else "materialization",
                )

            # Try to create a MaterializingTask for asset-eligible nodes.
            if self._disable_assets:
                asset_task, asset_key = None, None
            else:
                asset_task, asset_key = _build_asset_task(node, with_opts)
            if asset_task is not None:
                node_task = asset_task
            else:
                asset_key = None
                node_task = base_task.with_options(**with_opts)

            future = runner.submit(
                node_task,
                parameters={
                    "node": node,
                    "command": command,
                    "full_refresh": full_refresh,
                    "target": target,
                    "asset_key": asset_key,
                    "extra_cli_args": extra_cli_args,
                },
            )
            return future

        def _process_future_result(node_id, future):
            """Process a completed future — same logic as the old wave collector."""
            try:
                node_result = future.result()
                result_token = node_result.get("_build_run_id")
                if result_token != build_run_id:
                    # Cache hit — copy before mutating to avoid corrupting
                    # the stored value.
                    node_result = {
                        k: v for k, v in node_result.items() if k != "_build_run_id"
                    }
                    node_result["status"] = "cached"
                else:
                    node_result.pop("_build_run_id", None)
                    if node_id in computed_cache_keys:
                        execution_state[node_id] = computed_cache_keys[node_id]
                results[node_id] = node_result
                self._run_hooks(
                    "after_node_orchestration",
                    node_id=node_id,
                    result=results[node_id],
                    orchestrator=self,
                )
                _maybe_emit_after_wave(node_id)
            except _DbtNodeError as exc:
                artifact_msg = (
                    (exc.execution_result.artifacts or {})
                    .get(node_id, {})
                    .get("message")
                ) or None
                error_info = {
                    "message": artifact_msg
                    or (
                        str(exc.execution_result.error)
                        if exc.execution_result.error
                        else "unknown error"
                    ),
                    "type": type(exc.execution_result.error).__name__
                    if exc.execution_result.error
                    else "UnknownError",
                }
                results[node_id] = build_result(
                    status="error",
                    timing=exc.timing,
                    invocation=exc.invocation,
                    error=error_info,
                )
                self._run_hooks(
                    "after_node_orchestration",
                    node_id=node_id,
                    result=results[node_id],
                    orchestrator=self,
                )
                _maybe_emit_after_wave(node_id)
                execution_state.pop(node_id, None)
                _mark_failed(node_id)
            except Exception as exc:
                results[node_id] = build_result(
                    status="error",
                    error={
                        "message": str(exc),
                        "type": type(exc).__name__,
                    },
                )
                self._run_hooks(
                    "after_node_orchestration",
                    node_id=node_id,
                    result=results[node_id],
                    orchestrator=self,
                )
                _maybe_emit_after_wave(node_id)
                execution_state.pop(node_id, None)
                _mark_failed(node_id)

        with (
            temporary_settings(
                updates={PREFECT_CLIENT_SERVER_VERSION_CHECK_ENABLED: False}
            ),
            task_runner as runner,
        ):
            for phase_nodes in phases:
                # Build in-degree and dependents maps for this phase.
                in_degree: dict[str, int] = {}
                dependents: dict[str, list[str]] = {nid: [] for nid in phase_nodes}
                for nid, node in phase_nodes.items():
                    deps_in_phase = [d for d in node.depends_on if d in phase_nodes]
                    in_degree[nid] = len(deps_in_phase)
                    for dep in deps_in_phase:
                        dependents[dep].append(nid)

                # Completion queue: callbacks append here, main thread drains.
                active_futures: dict[int, tuple[object, str]] = {}
                completed_queue: deque[tuple[object, str]] = deque()
                completion_event = threading.Event()

                def _on_complete(
                    future, *, _nid, _queue=completed_queue, _event=completion_event
                ):
                    _queue.append((future, _nid))
                    _event.set()

                def _propagate(completed_nid):
                    """Decrement in-degree of dependents; submit newly ready nodes.

                    Uses an iterative BFS to avoid recursion when cascading
                    skips propagate through long dependency chains.
                    """
                    propagation_queue: deque[str] = deque([completed_nid])
                    while propagation_queue:
                        source_nid = propagation_queue.popleft()
                        for dep_nid in dependents.get(source_nid, []):
                            in_degree[dep_nid] -= 1
                            if in_degree[dep_nid] == 0:
                                node = phase_nodes[dep_nid]
                                upstream_failures = [
                                    dep
                                    for dep in node.depends_on
                                    if dep in failed_nodes
                                ]
                                if upstream_failures:
                                    results[node.unique_id] = build_result(
                                        status="skipped",
                                        reason="upstream failure",
                                        failed_upstream=upstream_failures,
                                    )
                                    _maybe_emit_after_wave(node.unique_id)
                                    failed_nodes.add(node.unique_id)
                                    propagation_queue.append(dep_nid)
                                else:
                                    future = _submit_node(node, runner)
                                    future.add_done_callback(
                                        partial(_on_complete, _nid=dep_nid)
                                    )
                                    active_futures[id(future)] = (future, dep_nid)

                # Submit root nodes (in_degree == 0).
                for nid, degree in in_degree.items():
                    if degree == 0:
                        node = phase_nodes[nid]
                        # Root nodes have no in-phase deps so upstream
                        # failures only matter across phases (already in
                        # failed_nodes from a prior phase).
                        upstream_failures = [
                            dep for dep in node.depends_on if dep in failed_nodes
                        ]
                        if upstream_failures:
                            results[node.unique_id] = build_result(
                                status="skipped",
                                reason="upstream failure",
                                failed_upstream=upstream_failures,
                            )
                            _maybe_emit_after_wave(node.unique_id)
                            failed_nodes.add(node.unique_id)
                            _propagate(nid)
                        else:
                            future = _submit_node(node, runner)
                            future.add_done_callback(partial(_on_complete, _nid=nid))
                            active_futures[id(future)] = (future, nid)

                # Process completions eagerly — no wave barriers.
                while active_futures:
                    completion_event.wait()
                    completion_event.clear()
                    while completed_queue:
                        future, nid = completed_queue.popleft()
                        active_futures.pop(id(future), None)
                        _process_future_result(nid, future)
                        _propagate(nid)

                # Safety: verify every node in this phase was processed.
                missing = set(phase_nodes) - set(results) - failed_nodes
                if missing:
                    raise RuntimeError(
                        f"Eager scheduler failed to process {len(missing)} nodes"
                    )

        if self._cache is not None:
            self._save_execution_state(execution_state)

        return results

    def _determine_per_node_max_workers(
        self, task_runner_type: type, largest_wave: int
    ) -> int:
        """Determine max_workers for PER_NODE task submission."""
        cpu_count = os.cpu_count()

        if isinstance(self._concurrency, int):
            # Respect explicit user-provided worker counts.
            return max(1, self._concurrency)
        elif isinstance(self._concurrency, str):
            # Named concurrency limit: the server-side limit throttles
            # execution, so clamp the pool to avoid spawning an excessive
            # number of idle processes on large DAGs.
            max_workers = min(largest_wave, cpu_count or 4)
        else:
            max_workers = largest_wave

        if isinstance(task_runner_type, type) and issubclass(
            task_runner_type, ProcessPoolTaskRunner
        ):
            max_workers = min(max_workers, (cpu_count or 1) * 2)
            # Windows ProcessPoolExecutor hard-caps max_workers at 61.
            if sys.platform == "win32":
                max_workers = min(max_workers, 61)

        return max(1, max_workers)
