"""
Executor for running dbt commands on individual nodes or waves.

This module provides:
- ExecutionResult: Result of a dbt command execution
- DbtExecutor: Protocol for dbt execution backends
- DbtCoreExecutor: Implementation using dbt-core's dbtRunner
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from dbt.cli.main import dbtRunner

from prefect_dbt.core._manifest import DbtNode
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import kwargs_to_args


@dataclass
class ExecutionResult:
    """Result of executing one or more dbt nodes.

    Attributes:
        success: Whether the execution completed successfully
        node_ids: List of unique_ids that were executed
        error: Exception captured on failure (None on success)
        artifacts: Per-node result data extracted from dbt's RunExecutionResult.
            Maps unique_id to {status, message, execution_time}.
    """

    success: bool
    node_ids: list[str] = field(default_factory=list)
    error: Exception | None = None
    artifacts: dict[str, Any] | None = None


@runtime_checkable
class DbtExecutor(Protocol):
    """Protocol for dbt execution backends."""

    def execute_node(
        self, node: DbtNode, command: str, full_refresh: bool = False
    ) -> ExecutionResult: ...

    def execute_wave(
        self, nodes: list[DbtNode], full_refresh: bool = False
    ) -> ExecutionResult: ...


class DbtCoreExecutor:
    """Execute dbt commands via dbt-core's dbtRunner.

    This is a thin wrapper that constructs CLI args, invokes dbt, and
    captures results. It does not create Prefect tasks or callbacks —
    that is the orchestrator's responsibility.

    Args:
        settings: PrefectDbtSettings with project_dir, profiles_dir, etc.
        threads: Number of dbt threads (omitted if None, uses dbt default)
        state_path: Path for --state flag (deferred state comparison)
        defer: Whether to pass --defer flag
        defer_state_path: Path for --defer-state flag
        favor_state: Whether to pass --favor-state flag
    """

    # Commands that accept the --full-refresh flag.
    _FULL_REFRESH_COMMANDS = frozenset({"run", "build", "seed"})

    def __init__(
        self,
        settings: PrefectDbtSettings,
        threads: int | None = None,
        state_path: Path | None = None,
        defer: bool = False,
        defer_state_path: Path | None = None,
        favor_state: bool = False,
    ):
        self._settings = settings
        self._threads = threads
        self._state_path = state_path
        self._defer = defer
        self._defer_state_path = defer_state_path
        self._favor_state = favor_state

    def _invoke(
        self,
        command: str,
        node_ids: list[str],
        selectors: list[str],
        full_refresh: bool = False,
    ) -> ExecutionResult:
        """Build CLI args and invoke dbt.

        Constructs a fresh kwargs dict each call (kwargs_to_args mutates it),
        resolves profiles, and runs dbt via a fresh dbtRunner instance.

        Errors are captured as data — this method does NOT raise.

        Args:
            command: dbt command to run (e.g. "build", "run", "seed")
            node_ids: List of node unique_ids for tracking in the result
            selectors: List of dbt selectors for `--select`
            full_refresh: Whether to pass --full-refresh
        """
        invoke_kwargs: dict[str, Any] = {
            "project_dir": str(self._settings.project_dir),
            "target_path": str(self._settings.target_path),
            "log_level": "none",
            "log_level_file": str(self._settings.log_level.value),
            "select": selectors,
        }

        if self._threads is not None:
            invoke_kwargs["threads"] = self._threads
        if full_refresh and command in self._FULL_REFRESH_COMMANDS:
            invoke_kwargs["full_refresh"] = True
        if self._state_path is not None:
            invoke_kwargs["state"] = str(self._state_path)
        if self._defer:
            invoke_kwargs["defer"] = True
        if self._defer_state_path is not None:
            invoke_kwargs["defer_state"] = str(self._defer_state_path)
        if self._favor_state:
            invoke_kwargs["favor_state"] = True

        try:
            with self._settings.resolve_profiles_yml() as profiles_dir:
                invoke_kwargs["profiles_dir"] = profiles_dir
                args = kwargs_to_args(invoke_kwargs, [command])
                res = dbtRunner().invoke(args)

            artifacts = self._extract_artifacts(res)
            # Union of requested nodes and actually-executed nodes.  The
            # node_ids list is always included so callers can rely on every
            # requested node appearing in the result.  Artifacts may add
            # extra entries (e.g. tests attached to selected models).
            if artifacts:
                result_ids = list(dict.fromkeys(node_ids + list(artifacts)))
            else:
                result_ids = list(node_ids)

            return ExecutionResult(
                success=res.success,
                node_ids=result_ids,
                error=res.exception if not res.success else None,
                artifacts=artifacts,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                node_ids=list(node_ids),
                error=exc,
            )

    def _extract_artifacts(self, res: Any) -> dict[str, Any] | None:
        """Extract per-node result data from dbt's RunExecutionResult."""
        if res.result is None or not hasattr(res.result, "results"):
            return None
        if not res.result.results:
            return None

        artifacts: dict[str, Any] = {}
        for node_result in res.result.results:
            uid = getattr(node_result, "unique_id", None)
            if uid is None:
                node = getattr(node_result, "node", None)
                uid = getattr(node, "unique_id", None) if node else None
            if uid is None:
                continue
            artifacts[uid] = {
                "status": str(getattr(node_result, "status", "")),
                "message": getattr(node_result, "message", ""),
                "execution_time": getattr(node_result, "execution_time", 0.0),
            }
        return artifacts or None

    def execute_node(
        self, node: DbtNode, command: str, full_refresh: bool = False
    ) -> ExecutionResult:
        """Execute a single dbt node with the specified command.

        Args:
            node: The DbtNode to execute
            command: dbt command ("run", "seed", "snapshot", "test")
            full_refresh: Whether to pass --full-refresh (ignored for
                commands that don't support it, like "test" and "snapshot")

        Returns:
            ExecutionResult with success/failure status and artifacts
        """
        return self._invoke(
            command,
            node_ids=[node.unique_id],
            selectors=[node.dbt_selector],
            full_refresh=full_refresh,
        )

    def execute_wave(
        self, nodes: list[DbtNode], full_refresh: bool = False
    ) -> ExecutionResult:
        """Execute a wave of nodes using `dbt build`.

        Uses `dbt build` to handle mixed resource types in a single invocation.

        Args:
            nodes: List of DbtNode objects to execute
            full_refresh: Whether to pass --full-refresh

        Returns:
            ExecutionResult with success/failure status and artifacts

        Raises:
            ValueError: If nodes list is empty
        """
        if not nodes:
            raise ValueError("Cannot execute an empty wave")

        node_ids = [node.unique_id for node in nodes]
        selectors = [node.dbt_selector for node in nodes]
        return self._invoke(
            "build", node_ids=node_ids, selectors=selectors, full_refresh=full_refresh
        )
