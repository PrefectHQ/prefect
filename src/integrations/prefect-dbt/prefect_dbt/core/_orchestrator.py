"""
Orchestrator for per-node and per-wave dbt execution.

This module provides:
- ExecutionMode: Constants for execution mode selection
- PrefectDbtOrchestrator: Executes dbt builds with wave or per-node execution
"""

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from dbt.artifacts.resources.types import NodeType

from prefect_dbt.core._executor import DbtCoreExecutor, DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import ManifestParser, resolve_selection
from prefect_dbt.core.settings import PrefectDbtSettings


class ExecutionMode:
    """Execution mode for dbt orchestration.

    PER_WAVE: Each wave is a single ``dbt build`` invocation containing all
        nodes in the wave.  Lower overhead, but a single failure marks the
        entire wave as failed and retries are not per-node.

    PER_NODE: Each node is a separate Prefect task with individual retries
        and concurrency control.  Requires ``run_build()`` to be called
        inside a ``@flow``.
    """

    PER_NODE = "per_node"
    PER_WAVE = "per_wave"


# Map executable node types to their dbt CLI commands.
_NODE_COMMAND = {
    NodeType.Model: "run",
    NodeType.Seed: "seed",
    NodeType.Snapshot: "snapshot",
}


class _DbtNodeError(Exception):
    """Raised inside per-node tasks to trigger Prefect retries.

    Carries execution details so the orchestrator can build a proper
    error result after all retries are exhausted.
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


class PrefectDbtOrchestrator:
    """Orchestrate dbt builds wave-by-wave or per-node.

    Wires together ManifestParser (Phase 1), resolve_selection (Phase 2),
    and DbtExecutor (Phase 3) to execute a full dbt build in topological
    wave order.

    Supports two execution modes:

    - **PER_WAVE** (default): Each wave is a single ``dbt build`` invocation.
      Lower overhead but coarser failure granularity.
    - **PER_NODE**: Each node is a separate Prefect task with individual
      retries and concurrency control.  Requires ``run_build()`` to be
      called inside a ``@flow``.

    Args:
        settings: PrefectDbtSettings instance (created with defaults if None)
        manifest_path: Explicit path to manifest.json (auto-detected if None)
        executor: DbtExecutor implementation (DbtCoreExecutor created if None)
        threads: Number of dbt threads (forwarded to DbtCoreExecutor)
        state_path: Path for --state flag
        defer: Whether to pass --defer flag
        defer_state_path: Path for --defer-state flag
        favor_state: Whether to pass --favor-state flag
        execution_mode: ``ExecutionMode.PER_WAVE`` or ``ExecutionMode.PER_NODE``
        retries: Number of retries per node (PER_NODE mode only)
        retry_delay_seconds: Delay between retries in seconds
        concurrency: Concurrency limit.  A string names an existing Prefect
            global concurrency limit; an int sets the max_workers on the
            ProcessPoolTaskRunner used for parallel node execution.
        task_runner_type: Task runner class to use for PER_NODE execution.
            Defaults to ``ProcessPoolTaskRunner``.

    Example::

        @flow
        def run_dbt_build():
            orchestrator = PrefectDbtOrchestrator(
                execution_mode=ExecutionMode.PER_NODE,
                retries=2,
                concurrency=4,
            )
            return orchestrator.run_build()
    """

    def __init__(
        self,
        settings: Optional[PrefectDbtSettings] = None,
        manifest_path: Optional[Path] = None,
        executor: Optional[DbtExecutor] = None,
        threads: Optional[int] = None,
        state_path: Optional[Path] = None,
        defer: bool = False,
        defer_state_path: Optional[Path] = None,
        favor_state: bool = False,
        execution_mode: str = ExecutionMode.PER_WAVE,
        retries: int = 0,
        retry_delay_seconds: int = 30,
        concurrency: Optional[Union[str, int]] = None,
        task_runner_type: Optional[type] = None,
    ):
        self._settings = (settings or PrefectDbtSettings()).model_copy()
        self._manifest_path = manifest_path
        self._execution_mode = execution_mode
        self._retries = retries
        self._retry_delay_seconds = retry_delay_seconds
        self._concurrency = concurrency
        self._task_runner_type = task_runner_type

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

    @staticmethod
    def _build_node_result(
        status: str,
        timing: Optional[dict[str, Any]] = None,
        invocation: Optional[dict[str, Any]] = None,
        error: Optional[dict[str, Any]] = None,
        reason: Optional[str] = None,
        failed_upstream: Optional[list[str]] = None,
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

    def _resolve_target_path(self) -> Path:
        """Resolve the target directory path.

        When ``manifest_path`` is explicitly set, normalizes it to an absolute
        path (relative to ``settings.project_dir``) and returns its parent
        directory so that ``resolve_selection`` uses the same target directory
        as the manifest. Otherwise, returns ``settings.target_path``.
        """
        if self._manifest_path is not None:
            if self._manifest_path.is_absolute():
                return self._manifest_path.parent
            return (self._settings.project_dir / self._manifest_path).resolve().parent
        return self._settings.target_path

    def _resolve_manifest_path(self) -> Path:
        """Resolve the path to manifest.json.

        Uses the explicit ``manifest_path`` if provided (relative paths are
        resolved against ``settings.project_dir``), otherwise derives it from
        ``settings.project_dir / settings.target_path / "manifest.json"``.

        Returns:
            Resolved Path to the manifest.json file

        Raises:
            FileNotFoundError: If the manifest file does not exist
        """
        if self._manifest_path is not None:
            if self._manifest_path.is_absolute():
                path = self._manifest_path
            else:
                path = self._settings.project_dir / self._manifest_path
        else:
            path = (
                self._settings.project_dir
                / self._settings.target_path
                / "manifest.json"
            )

        if not path.exists():
            raise FileNotFoundError(
                f"Manifest file not found: {path}. "
                f"Run 'dbt compile' or 'dbt parse' to generate it."
            )
        return path

    def run_build(
        self,
        select: Optional[str] = None,
        exclude: Optional[str] = None,
        full_refresh: bool = False,
    ) -> dict[str, Any]:
        """Execute a dbt build wave-by-wave or per-node.

        Pipeline:
        1. Parse the manifest
        2. Optionally resolve selectors to filter nodes
        3. Compute execution waves (topological order)
        4. Execute (per-wave or per-node depending on mode)

        In **PER_NODE** mode, each node becomes a separate Prefect task with
        individual retries.  This requires ``run_build()`` to be called
        inside a ``@flow``.

        Args:
            select: dbt selector expression (e.g. ``"tag:daily"``)
            exclude: dbt exclude expression
            full_refresh: Whether to pass ``--full-refresh`` to dbt

        Returns:
            Dict mapping node unique_id to result dict. Each result has:
            - ``status``: ``"success"``, ``"error"``, or ``"skipped"``
            - ``timing``: ``{started_at, completed_at, duration_seconds}``
              (not present for skipped nodes)
            - ``invocation``: ``{command, args}`` (not present for skipped)
            - ``error``: ``{message, type}`` (only for error status)
            - ``reason``: reason string (only for skipped status)
            - ``failed_upstream``: list of failed node IDs (only for skipped)
        """
        # 1. Parse manifest
        manifest_path = self._resolve_manifest_path()
        parser = ManifestParser(manifest_path)

        # 2. Resolve selectors if provided
        selected_ids: Optional[set[str]] = None
        if select is not None or exclude is not None:
            with self._settings.resolve_profiles_yml() as resolved_profiles_dir:
                selected_ids = resolve_selection(
                    project_dir=self._settings.project_dir,
                    profiles_dir=Path(resolved_profiles_dir),
                    select=select,
                    exclude=exclude,
                    target_path=self._resolve_target_path(),
                )

        # 3. Filter nodes and compute waves
        filtered_nodes = parser.filter_nodes(selected_node_ids=selected_ids)
        waves = parser.compute_execution_waves(nodes=filtered_nodes)

        # 4. Execute
        if self._execution_mode == ExecutionMode.PER_NODE:
            return self._execute_per_node(waves, full_refresh)
        return self._execute_per_wave(waves, full_refresh)

    # ------------------------------------------------------------------
    # PER_WAVE execution
    # ------------------------------------------------------------------

    def _execute_per_wave(self, waves, full_refresh):
        """Execute waves one at a time, each as a single dbt invocation."""
        results: dict[str, Any] = {}
        failed_nodes: list[str] = []

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
            try:
                wave_result: ExecutionResult = self._executor.execute_wave(
                    wave.nodes, full_refresh=full_refresh
                )
            except Exception as exc:
                wave_result = ExecutionResult(
                    success=False,
                    node_ids=[n.unique_id for n in wave.nodes],
                    error=exc,
                )
            completed_at = datetime.now(timezone.utc)

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
                # PER_WAVE: all nodes in wave marked as error
                error_info = {
                    "message": str(wave_result.error)
                    if wave_result.error
                    else "unknown error",
                    "type": type(wave_result.error).__name__
                    if wave_result.error
                    else "UnknownError",
                }
                for node in wave.nodes:
                    results[node.unique_id] = self._build_node_result(
                        status="error",
                        timing=dict(timing),
                        invocation=dict(invocation),
                        error=error_info,
                    )
                failed_nodes.extend(n.unique_id for n in wave.nodes)

        return results

    # ------------------------------------------------------------------
    # PER_NODE execution
    # ------------------------------------------------------------------

    def _execute_per_node(self, waves, full_refresh):
        """Execute each node as an individual Prefect task.

        Creates a separate Prefect task per node with individual retries.
        Nodes within a wave are submitted concurrently via a
        ``ProcessPoolTaskRunner``; waves are processed sequentially.  Failed
        nodes cause their downstream dependents to be skipped.

        Each subprocess gets its own dbt adapter registry (``FACTORY``
        singleton), so there is no shared mutable state and no need to
        monkey-patch ``adapter_management``.

        Requires an active Prefect flow run context (call inside a ``@flow``).
        """
        from prefect import task as prefect_task

        if self._task_runner_type is None:
            from prefect.task_runners import ProcessPoolTaskRunner

            task_runner_type = ProcessPoolTaskRunner
        else:
            task_runner_type = self._task_runner_type

        executor = self._executor
        concurrency_name = (
            self._concurrency if isinstance(self._concurrency, str) else None
        )
        build_result = self._build_node_result

        # Compute max_workers for the process pool.
        largest_wave = max((len(wave.nodes) for wave in waves), default=1)
        if isinstance(self._concurrency, int):
            max_workers = self._concurrency
        elif isinstance(self._concurrency, str):
            # Named concurrency limit: the server-side limit throttles
            # execution, so clamp the pool to avoid spawning an excessive
            # number of idle processes on large DAGs.
            import os

            max_workers = min(largest_wave, os.cpu_count() or 4)
        else:
            max_workers = largest_wave

        # Define the task function once; .with_options() customizes per node.
        @prefect_task
        def run_dbt_node(node, command, full_refresh):
            # Acquire named concurrency slot if configured
            if concurrency_name:
                from prefect.concurrency.sync import (
                    concurrency as prefect_concurrency,
                )

                ctx = prefect_concurrency(concurrency_name)
            else:
                ctx = nullcontext()

            started_at = datetime.now(timezone.utc)
            with ctx:
                result = executor.execute_node(node, command, full_refresh)
            completed_at = datetime.now(timezone.utc)

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

        results: dict[str, Any] = {}
        failed_nodes: set[str] = set()

        with task_runner_type(max_workers=max_workers) as runner:
            for wave in waves:
                futures: dict[str, Any] = {}

                for node in wave.nodes:
                    # Check if any upstream dependency has failed or been skipped
                    upstream_failures = [
                        dep for dep in node.depends_on if dep in failed_nodes
                    ]
                    if upstream_failures:
                        results[node.unique_id] = build_result(
                            status="skipped",
                            reason="upstream failure",
                            failed_upstream=upstream_failures,
                        )
                        failed_nodes.add(node.unique_id)
                        continue

                    command = _NODE_COMMAND.get(node.resource_type, "run")
                    node_task = run_dbt_node.with_options(
                        name=f"dbt_{command}_{node.name}",
                        retries=self._retries,
                        retry_delay_seconds=self._retry_delay_seconds,
                    )
                    future = runner.submit(
                        node_task,
                        parameters={
                            "node": node,
                            "command": command,
                            "full_refresh": full_refresh,
                        },
                    )
                    futures[node.unique_id] = future

                # Collect results for this wave
                for node_id, future in futures.items():
                    try:
                        results[node_id] = future.result()
                    except _DbtNodeError as exc:
                        error_info = {
                            "message": str(exc.execution_result.error)
                            if exc.execution_result.error
                            else "unknown error",
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
                        failed_nodes.add(node_id)
                    except Exception as exc:
                        results[node_id] = build_result(
                            status="error",
                            error={
                                "message": str(exc),
                                "type": type(exc).__name__,
                            },
                        )
                        failed_nodes.add(node_id)

        return results
