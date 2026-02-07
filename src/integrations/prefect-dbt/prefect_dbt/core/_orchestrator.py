"""
Orchestrator for per-node dbt execution in PER_WAVE mode.

This module provides:
- PrefectDbtOrchestrator: Executes dbt builds wave-by-wave, wiring together
  ManifestParser, resolve_selection, and DbtExecutor from Phases 1-3.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from prefect_dbt.core._executor import DbtCoreExecutor, DbtExecutor, ExecutionResult
from prefect_dbt.core._manifest import ManifestParser, resolve_selection
from prefect_dbt.core.settings import PrefectDbtSettings


class PrefectDbtOrchestrator:
    """Orchestrate dbt builds wave-by-wave (PER_WAVE mode).

    Wires together ManifestParser (Phase 1), resolve_selection (Phase 2),
    and DbtExecutor (Phase 3) to execute a full dbt build in topological
    wave order. Downstream waves are skipped on failure.

    This is a plain class — the user wraps ``run_build()`` in their own
    ``@flow`` as needed.

    Args:
        settings: PrefectDbtSettings instance (created with defaults if None)
        manifest_path: Explicit path to manifest.json (auto-detected if None)
        executor: DbtExecutor implementation (DbtCoreExecutor created if None)
        threads: Number of dbt threads (forwarded to DbtCoreExecutor)
        state_path: Path for --state flag
        defer: Whether to pass --defer flag
        defer_state_path: Path for --defer-state flag
        favor_state: Whether to pass --favor-state flag

    Example:
        orchestrator = PrefectDbtOrchestrator()
        result = orchestrator.run_build(select="tag:daily")
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
    ):
        self._settings = (settings or PrefectDbtSettings()).model_copy()
        self._manifest_path = manifest_path

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
        """Execute a dbt build wave-by-wave.

        Pipeline:
        1. Parse the manifest
        2. Optionally resolve selectors to filter nodes
        3. Compute execution waves (topological order)
        4. Execute each wave; skip downstream waves on failure

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
            selected_ids = resolve_selection(
                project_dir=self._settings.project_dir,
                profiles_dir=self._settings.profiles_dir,
                select=select,
                exclude=exclude,
                target_path=self._resolve_target_path(),
            )

        # 3. Filter nodes and compute waves
        filtered_nodes = parser.filter_nodes(selected_node_ids=selected_ids)
        waves = parser.compute_execution_waves(nodes=filtered_nodes)

        # 4. Execute waves
        results: dict[str, Any] = {}
        failed_nodes: list[str] = []

        for wave in waves:
            if failed_nodes:
                # Skip this wave — upstream failure
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
