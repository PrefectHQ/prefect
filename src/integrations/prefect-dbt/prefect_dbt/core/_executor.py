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
from dbt_common.events.base_types import EventLevel, EventMsg

from prefect.logging import get_logger
from prefect_dbt.core._manifest import DbtNode
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import kwargs_to_args

logger = get_logger(__name__)

_EVENT_LEVEL_MAP: dict[EventLevel, str] = {
    EventLevel.DEBUG: "debug",
    EventLevel.TEST: "debug",
    EventLevel.INFO: "info",
    EventLevel.WARN: "warning",
    EventLevel.ERROR: "error",
}

_EVENT_LEVEL_PRIORITY: dict[EventLevel, int] = {
    EventLevel.DEBUG: 0,
    EventLevel.TEST: 1,
    EventLevel.INFO: 2,
    EventLevel.WARN: 3,
    EventLevel.ERROR: 4,
}


@dataclass
class ExecutionResult:
    """Result of executing one or more dbt nodes.

    Attributes:
        success: Whether the execution completed successfully
        node_ids: List of unique_ids that were executed
        error: Exception captured on failure (None on success)
        artifacts: Per-node result data extracted from dbt's RunExecutionResult.
            Maps unique_id to {status, message, execution_time}.
        log_messages: Per-node captured dbt log messages.
            Maps unique_id to list of (level, message) tuples.
            Messages not associated with a specific node use an empty string as a key.
    """

    success: bool
    node_ids: list[str] = field(default_factory=list)
    error: Exception | None = None
    artifacts: dict[str, Any] | None = None
    log_messages: dict[str, list[tuple[str, str]]] | None = None


@runtime_checkable
class DbtExecutor(Protocol):
    """Protocol for dbt execution backends."""

    def execute_node(
        self,
        node: DbtNode,
        command: str,
        full_refresh: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult: ...

    def execute_wave(
        self,
        nodes: list[DbtNode],
        full_refresh: bool = False,
        indirect_selection: str | None = None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult: ...

    def resolve_manifest_path(self) -> Path: ...


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
        self._settings.validate_for_orchestrator()
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
        indirect_selection: str | None = None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
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
            indirect_selection: dbt indirect selection mode (e.g. "empty"
                to suppress automatic test inclusion)
            target: dbt target name to override the default from
                profiles.yml (maps to `--target` / `-t`)
            extra_cli_args: Additional CLI arguments to append after the
                base args built by kwargs_to_args()
        """
        invoke_kwargs: dict[str, Any] = {
            "project_dir": str(self._settings.project_dir),
            "target_path": str(self._settings.target_path),
            "log_level": "none",
            "log_level_file": str(self._settings.log_level.value),
            "select": selectors,
        }
        if indirect_selection is not None:
            invoke_kwargs["indirect_selection"] = indirect_selection
        if target is not None:
            invoke_kwargs["target"] = target

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
            captured_logs: dict[str, list[tuple[str, str]]] = {}
            min_priority = _EVENT_LEVEL_PRIORITY.get(self._settings.log_level, 2)

            def _capture_event(event: EventMsg) -> None:
                try:
                    event_priority = _EVENT_LEVEL_PRIORITY.get(event.info.level, -1)
                    if event_priority < min_priority:
                        return
                    msg = event.info.msg
                    if not msg or (isinstance(msg, str) and not msg.strip()):
                        return
                    level_str = _EVENT_LEVEL_MAP.get(event.info.level, "info")
                    try:
                        node_id = event.data.node_info.unique_id or ""
                    except Exception:
                        node_id = ""
                    captured_logs.setdefault(node_id, []).append((level_str, str(msg)))
                except Exception:
                    pass

            with self._settings.resolve_profiles_yml() as profiles_dir:
                invoke_kwargs["profiles_dir"] = profiles_dir
                args = kwargs_to_args(invoke_kwargs, [command])
                if extra_cli_args:
                    args.extend(extra_cli_args)
                res = dbtRunner(callbacks=[_capture_event]).invoke(args)

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
                log_messages=captured_logs or None,
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
        self,
        node: DbtNode,
        command: str,
        full_refresh: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a single dbt node with the specified command.

        Args:
            node: The DbtNode to execute
            command: dbt command ("run", "seed", "snapshot", "test")
            full_refresh: Whether to pass --full-refresh (ignored for
                commands that don't support it, like "test" and "snapshot")
            target: dbt target name (`--target` / `-t`)
            extra_cli_args: Additional CLI arguments to append

        Returns:
            ExecutionResult with success/failure status and artifacts
        """
        return self._invoke(
            command,
            node_ids=[node.unique_id],
            selectors=[node.dbt_selector],
            full_refresh=full_refresh,
            target=target,
            extra_cli_args=extra_cli_args,
        )

    def resolve_manifest_path(self) -> Path:
        """Return the path to manifest.json, running 'dbt parse' if it doesn't exist.

        Resolves to `settings.project_dir / settings.target_path / manifest.json`.
        If the file is not found, runs `dbt parse` to generate it.

        Returns:
            Resolved absolute `Path` to `manifest.json`.

        Raises:
            RuntimeError: If `dbt parse` fails or the manifest is still
                missing after a successful parse.
        """
        path = (
            self._settings.project_dir / self._settings.target_path / "manifest.json"
        ).resolve()
        if not path.exists():
            self._run_parse(path)
        return path

    def _run_parse(self, expected_path: Path) -> None:
        """Run `dbt parse` to generate a manifest at *expected_path*.

        Args:
            expected_path: Where the manifest should appear after parsing.
                Used only for validation and error reporting.

        Raises:
            RuntimeError: If the `dbt parse` invocation fails or the
                manifest file is still missing after a successful parse.
        """
        logger.info(
            "Manifest not found at %s; running 'dbt parse' to generate it.",
            expected_path,
        )
        with self._settings.resolve_profiles_yml() as profiles_dir:
            args = [
                "parse",
                "--project-dir",
                str(self._settings.project_dir),
                "--profiles-dir",
                profiles_dir,
                "--target-path",
                str(self._settings.target_path),
                "--log-level",
                "none",
                "--log-level-file",
                str(self._settings.log_level.value),
            ]
            result = dbtRunner().invoke(args)

        if not result.success:
            raise RuntimeError(
                f"Failed to generate manifest via 'dbt parse': {result.exception}"
            )

        if not expected_path.exists():
            raise RuntimeError(
                f"'dbt parse' succeeded but manifest not found at {expected_path}."
            )

    def execute_wave(
        self,
        nodes: list[DbtNode],
        full_refresh: bool = False,
        indirect_selection: str | None = None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a wave of nodes using `dbt build`.

        Uses `dbt build` to handle mixed resource types in a single invocation.

        Args:
            nodes: List of DbtNode objects to execute
            full_refresh: Whether to pass --full-refresh
            indirect_selection: dbt indirect selection mode.  Pass
                `"empty"` to prevent dbt from automatically including
                tests attached to selected models.
            target: dbt target name (`--target` / `-t`)
            extra_cli_args: Additional CLI arguments to append

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
            "build",
            node_ids=node_ids,
            selectors=selectors,
            full_refresh=full_refresh,
            indirect_selection=indirect_selection,
            target=target,
            extra_cli_args=extra_cli_args,
        )
