"""
Runner for dbt commands
"""

import json
import os
import threading
import time
from typing import Any, Callable, Optional, TypeVar

from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import (
    FreshnessStatus,
    NodeStatus,
    RunStatus,
    TestStatus,
)
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel, EventMsg
from google.protobuf.json_format import MessageToDict

from prefect import get_client, get_run_logger
from prefect.assets import Asset, AssetProperties
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import State
from prefect.context import AssetContext, hydrated_context, serialize_context
from prefect.events.related import related_resources_from_run_context
from prefect.exceptions import MissingContextError
from prefect.task_engine import run_task_sync
from prefect.tasks import MaterializingTask, Task, TaskOptions
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_dbt.core.profiles import aresolve_profiles_yml, resolve_profiles_yml
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import format_resource_id

FAILURE_STATUSES = [
    RunStatus.Error,
    TestStatus.Error,
    TestStatus.Fail,
    FreshnessStatus.Error,
    FreshnessStatus.RuntimeErr,
    NodeStatus.Error,
    NodeStatus.Fail,
    NodeStatus.RuntimeErr,
]
NODE_TYPES_TO_CALL_MATERIALIZATION_TASKS = [
    NodeType.Model,
    NodeType.Seed,
    NodeType.Snapshot,
]
NODE_TYPES_TO_EMIT_OBSERVATION_EVENTS = [
    NodeType.Exposure,
    NodeType.Source,
]
FAILURE_MSG = '{resource_type} {resource_name} {status}ed with message: "{message}"'

T = TypeVar("T")


class TaskState:
    """State for managing tasks across callbacks."""

    def __init__(self):
        self._tasks: dict[str, Task[Any, Any]] = {}
        self._task_loggers: dict[str, Any] = {}
        self._task_results: dict[str, Any] = {}
        self._node_status: dict[str, dict[str, Any]] = {}
        self._node_complete: dict[str, bool] = {}
        self._node_results: dict[str, Any] = {}
        self._node_dependencies: dict[str, list[str]] = {}
        # self._task_threads: dict[str, threading.Thread] = {}

    def start_task(self, node_id: str, task: Task[Any, Any]) -> None:
        """Start a task for a node."""
        self._tasks[node_id] = task
        self._node_complete[node_id] = False

    def get_task(self, node_id: str) -> Task[Any, Any] | None:
        """Get the task for a node."""
        return self._tasks.get(node_id)

    def end_task(self, node_id: str) -> None:
        """End a task for a node."""
        self._tasks.pop(node_id, None)
        self._task_loggers.pop(node_id, None)
        self._node_complete[node_id] = True
        # thread = self._task_threads.pop(node_id, None)
        # if thread and thread.is_alive():
        #     thread.join()

    def set_task_logger(self, node_id: str, logger: Any) -> None:
        """Set the logger for a task."""
        self._task_loggers[node_id] = logger

    def get_task_logger(self, node_id: str) -> Any | None:
        """Get the logger for a task."""
        return self._task_loggers.get(node_id)

    def set_node_status(
        self, node_id: str, event_data: dict[str, Any], event_message: str
    ) -> None:
        """Set the status for a node."""
        self._node_status[node_id] = {
            "event_data": event_data,
            "event_message": event_message,
        }
        # Mark node as complete when status is set
        self._node_complete[node_id] = True

    def get_node_status(self, node_id: str) -> dict[str, Any] | None:
        """Get the status for a node."""
        return self._node_status.get(node_id)

    def is_node_complete(self, node_id: str) -> bool:
        """Check if a node is complete."""
        return self._node_complete.get(node_id, False)

    def set_task_result(self, node_id: str, result: Any) -> None:
        """Set the result for a task."""
        self._task_results[node_id] = result

    def get_task_result(self, node_id: str) -> Any | None:
        """Get the result for a task."""
        return self._task_results.get(node_id)

    def set_node_result(self, node_id: str, result: Any) -> None:
        """Set the result for a node."""
        self._node_results[node_id] = result

    def get_node_result(self, node_id: str) -> Any | None:
        """Get the result for a node."""
        return self._node_results.get(node_id)

    def set_node_dependencies(self, node_id: str, dependencies: list[str]) -> None:
        """Set the dependencies for a node."""
        self._node_dependencies[node_id] = dependencies

    def get_node_dependencies(self, node_id: str) -> list[str]:
        """Get the dependencies for a node."""
        return self._node_dependencies.get(node_id, [])

    def get_all_nodes(self) -> list[str]:
        """Get all node IDs that have results."""
        return list(self._node_results.keys())

    def run_task_in_thread(
        self,
        node_id: str,
        task: Task[Any, Any],
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Run a task in a separate thread."""

        def run_task():
            try:
                with hydrated_context(context):
                    states: list[State] = []
                    dependencies = self.get_node_dependencies(node_id)
                    for dep_id in dependencies:
                        state = self.get_task_result(dep_id)
                        if state:
                            states.append(state)

                    state = run_task_sync(
                        task,
                        parameters=parameters,
                        wait_for=states,
                        context=context,
                        return_type="state",
                    )

                    # Wait for the task to complete
                    if state:
                        self.set_task_result(node_id, state)
                    else:
                        self.set_task_result(node_id, None)
            except Exception as e:
                self.set_task_result(node_id, e)

        thread = threading.Thread(target=run_task)
        thread.daemon = True
        # self._task_threads[node_id] = thread
        thread.start()


def execute_dbt_node(task_state: TaskState, node_id: str, asset_id: str | None):
    """Execute a dbt node and wait for its completion.

    This function will:
    1. Set up the task logger
    2. Wait for the node to finish by checking node status
    3. Check the node's status and fail if it's in a failure state
    """
    task_state.set_task_logger(node_id, get_run_logger())

    # Wait for the node to finish by checking node status
    while not task_state.is_node_complete(node_id):
        time.sleep(0.1)

    # Get the final status
    status = task_state.get_node_status(node_id)
    if status:
        node_info = status["event_data"].get("node_info", {})
        node_status = node_info.get("node_status")
        asset_context = AssetContext.get()
        if asset_context and asset_id:
            asset_context.add_asset_metadata(asset_id, node_info)

        if node_status in FAILURE_STATUSES:
            raise Exception(f"Node {node_id} finished with status {node_status}")


class PrefectDbtRunner:
    """A runner for executing dbt commands with Prefect integration.

    This class provides methods to run dbt commands while integrating with Prefect's
    logging and events capabilities. It handles manifest parsing, logging,
    and emitting events for dbt operations.

    Args:
        manifest: Optional pre-loaded dbt manifest
        settings: Optional PrefectDbtSettings instance for configuring dbt
        raise_on_failure: Whether to raise an error if the dbt command encounters a
            non-exception failure
        client: Optional Prefect client instance
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        settings: Optional[PrefectDbtSettings] = None,
        raise_on_failure: bool = True,
        client: Optional[PrefectClient] = None,
    ):
        self.settings = settings or PrefectDbtSettings()
        self._manifest: Optional[Manifest] = manifest
        self.client = client or get_client()
        self.raise_on_failure = raise_on_failure

    @property
    def manifest(self) -> Manifest:
        """Get the manifest, loading it from disk if necessary."""
        if self._manifest is None:
            self._set_manifest_from_project_dir()
            assert self._manifest is not None  # for type checking
        return self._manifest

    def _set_manifest_from_project_dir(self):
        """Set the manifest from the project directory"""
        try:
            with open(
                os.path.join(self.settings.project_dir, "target", "manifest.json"), "r"
            ) as f:
                self._manifest = Manifest.from_dict(json.load(f))  # type: ignore[reportUnknownMemberType]
        except FileNotFoundError:
            raise ValueError(
                f"Manifest file not found in {os.path.join(self.settings.project_dir, 'target', 'manifest.json')}"
            )

    def _get_node_prefect_config(
        self, manifest_node: ManifestNode
    ) -> dict[str, dict[str, Any]]:
        """Get the Prefect config for a given node"""
        return manifest_node.config.meta.get("prefect", {})

    def _get_upstream_manifest_nodes(
        self,
        manifest_node: ManifestNode,
    ) -> list[ManifestNode]:
        """Get upstream nodes for a given node"""
        upstream_manifest_nodes: list[ManifestNode] = []

        for depends_on_node in manifest_node.depends_on_nodes:  # type: ignore[reportUnknownMemberType]
            depends_manifest_node = self.manifest.nodes.get(depends_on_node)  # type: ignore[reportUnknownMemberType]

            if not depends_manifest_node or not self._get_node_prefect_config(
                depends_manifest_node
            ).get("emit_asset_events", True):
                continue

            if not depends_manifest_node.relation_name:
                raise ValueError("Relation name not found in manifest")

            upstream_manifest_nodes.append(depends_manifest_node)

        return upstream_manifest_nodes

    def _call_task(
        self,
        task_state: TaskState,
        manifest_node: ManifestNode,
        context: dict[str, Any],
        dbt_event: EventMsg,
    ):
        """Create and run a task for a node."""
        adapter_type = self.manifest.metadata.adapter_type
        if not adapter_type:
            raise ValueError("Adapter type not found in manifest")

        upstream_manifest_nodes = self._get_upstream_manifest_nodes(manifest_node)

        if manifest_node.resource_type in NODE_TYPES_TO_CALL_MATERIALIZATION_TASKS:
            if not manifest_node.relation_name:
                raise ValueError("Relation name not found in manifest")

            compiled_code_path = (
                self.settings.project_dir
                / "target"
                / "compiled"
                / str(self.settings.project_dir).split("/")[-1]
                / manifest_node.original_file_path
            )
            compiled_code = ""
            if os.path.exists(compiled_code_path):
                with open(compiled_code_path, "r") as f:
                    code_content = f.read()
                    compiled_code = (
                        f"\n ### Compiled code\n```sql\n{code_content.strip()}\n```"
                    )

            asset_id = format_resource_id(adapter_type, manifest_node.relation_name)

            asset = Asset(
                key=asset_id,
                properties=AssetProperties(
                    name=manifest_node.name,
                    description=manifest_node.description + compiled_code,
                    owners=[owner]
                    if (owner := manifest_node.config.meta.get("owner"))
                    and isinstance(owner, str)
                    else None,
                ),
            )

            upstream_assets: list[Asset] = []
            for upstream_manifest_node in upstream_manifest_nodes:
                if (
                    upstream_manifest_node.resource_type
                    in NODE_TYPES_TO_EMIT_OBSERVATION_EVENTS
                    or upstream_manifest_node.resource_type
                    in NODE_TYPES_TO_CALL_MATERIALIZATION_TASKS
                ):
                    if not upstream_manifest_node.relation_name:
                        raise ValueError("Relation name not found in manifest")
                    upstream_asset_id = format_resource_id(
                        adapter_type, upstream_manifest_node.relation_name
                    )

                    upstream_compiled_code_path = (
                        self.settings.project_dir
                        / "target"
                        / "compiled"
                        / str(self.settings.project_dir).split("/")[-1]
                        / upstream_manifest_node.original_file_path
                    )
                    upstream_compiled_code = ""
                    if os.path.exists(upstream_compiled_code_path):
                        with open(upstream_compiled_code_path, "r") as f:
                            upstream_code_content = f.read()
                            upstream_compiled_code = f"\n ### Compiled code\n```sql\n{upstream_code_content.strip()}\n```"

                    upstream_asset = Asset(
                        key=upstream_asset_id,
                        properties=AssetProperties(
                            name=upstream_manifest_node.name,
                            description=upstream_manifest_node.description
                            + upstream_compiled_code,
                            owners=[owner]
                            if (
                                owner := upstream_manifest_node.config.meta.get("owner")
                            )
                            and isinstance(owner, str)
                            else None,
                        ),
                    )
                    upstream_assets.append(upstream_asset)

            task_options = TaskOptions(
                task_run_name=f"Materialize {manifest_node.resource_type.lower()} {manifest_node.name if manifest_node.name else manifest_node.unique_id}",
                asset_deps=upstream_assets,
            )

            task = MaterializingTask(
                fn=execute_dbt_node,
                assets=[asset],
                materialized_by="dbt",
                **task_options,
            )

        else:
            asset_id = None
            task_options = TaskOptions(
                task_run_name=f"Execute {manifest_node.resource_type.lower()} {manifest_node.name if manifest_node.name else manifest_node.unique_id}",
            )
            task = Task(
                fn=execute_dbt_node,
                **task_options,
            )

        # Start the task in a separate thread
        task_state.start_task(manifest_node.unique_id, task)

        task_state.set_node_dependencies(
            manifest_node.unique_id,
            [node.unique_id for node in upstream_manifest_nodes],
        )

        print(
            f"Running task {manifest_node.unique_id} for node type {manifest_node.resource_type}"
        )

        task_state.run_task_in_thread(
            manifest_node.unique_id,
            task,
            parameters={
                "task_state": task_state,
                "node_id": manifest_node.unique_id,
                "asset_id": asset_id,
            },
            context=context,
        )

    @staticmethod
    def get_dbt_event_msg(event: EventMsg) -> str:
        return event.info.msg  # type: ignore[reportUnknownMemberType]

    def _create_logging_callback(
        self, task_state: TaskState, log_level: EventLevel, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for logging dbt events."""

        def logging_callback(event: EventMsg):
            event_data = MessageToDict(event.data, preserving_proto_field_name=True)
            if event_data.get("node_info"):
                node_id = self._get_dbt_event_node_id(event)
                logger = task_state.get_task_logger(node_id)
            else:
                try:
                    with hydrated_context(context) as run_context:
                        logger = get_run_logger(run_context)
                except MissingContextError:
                    logger = None

            if logger is not None:
                logger.setLevel(log_level.value.upper())
                if (
                    event.info.level == EventLevel.DEBUG
                    or event.info.level == EventLevel.TEST
                ):
                    logger.debug(self.get_dbt_event_msg(event))
                elif event.info.level == EventLevel.INFO:
                    logger.info(self.get_dbt_event_msg(event))
                elif event.info.level == EventLevel.WARN:
                    logger.warning(self.get_dbt_event_msg(event))
                elif event.info.level == EventLevel.ERROR:
                    logger.error(self.get_dbt_event_msg(event))

        return logging_callback

    def _get_dbt_event_node_id(self, event: EventMsg) -> str:
        return event.data.node_info.unique_id  # type: ignore[reportUnknownMemberType]

    def _create_node_started_callback(
        self, task_state: TaskState, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for starting tasks when nodes start."""

        def node_started_callback(event: EventMsg):
            if event.info.name == "NodeStart":
                node_id = self._get_dbt_event_node_id(event)
                assert isinstance(node_id, str)

                manifest_node = self.manifest.nodes.get(node_id)
                if manifest_node:
                    prefect_config = manifest_node.config.meta.get("prefect", {})
                    enable_assets = prefect_config.get("enable_assets", True)

                    try:
                        if enable_assets:
                            self._call_task(task_state, manifest_node, context, event)
                    except Exception as e:
                        print(e)

        return node_started_callback

    def _create_node_finished_callback(
        self, task_state: TaskState, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for ending tasks when nodes finish."""

        def node_finished_callback(event: EventMsg):
            if event.info.name == "NodeFinished":
                node_id = self._get_dbt_event_node_id(event)
                assert isinstance(node_id, str)

                manifest_node = self.manifest.nodes.get(node_id)
                if manifest_node:
                    prefect_config = manifest_node.config.meta.get("prefect", {})
                    enable_assets = prefect_config.get("enable_assets", True)

                    try:
                        if enable_assets:
                            # Store the status before ending the task
                            event_data = MessageToDict(
                                event.data, preserving_proto_field_name=True
                            )
                            event_message = self.get_dbt_event_msg(event)
                            task_state.set_node_status(
                                node_id, event_data, event_message
                            )
                            task_state.end_task(node_id)
                    except Exception as e:
                        print(e)

        return node_finished_callback

    async def ainvoke(self, args: list[str], **kwargs: Any) -> dbtRunnerResult:
        """Asynchronously invokes a dbt command."""
        context = serialize_context()
        task_state = TaskState()

        related_prefect_context = await related_resources_from_run_context(self.client)

        invoke_kwargs = {
            "project_dir": kwargs.pop("project_dir", self.settings.project_dir),
            "profiles_dir": kwargs.pop("profiles_dir", self.settings.profiles_dir),
            "log_level": kwargs.pop(
                "log_level",
                "none" if related_prefect_context else self.settings.log_level,
            ),
            **kwargs,
        }

        async with aresolve_profiles_yml(invoke_kwargs["profiles_dir"]) as profiles_dir:
            invoke_kwargs["profiles_dir"] = profiles_dir

            callbacks = [
                self._create_logging_callback(
                    task_state, self.settings.log_level, context
                ),
                self._create_node_started_callback(task_state, context),
                self._create_node_finished_callback(task_state, context),
            ]
            res = dbtRunner(callbacks=callbacks).invoke(args, **invoke_kwargs)  # type: ignore[reportUnknownMemberType]

            if not res.success and res.exception:
                raise ValueError(
                    f"Failed to invoke dbt command '{''.join(args)}': {res.exception}"
                )
            elif not res.success and self.raise_on_failure:
                assert isinstance(res.result, RunExecutionResult), (
                    "Expected run execution result from failed dbt invoke"
                )

                failure_results = [
                    FAILURE_MSG.format(
                        resource_type=result.node.resource_type.title(),
                        resource_name=result.node.name,
                        status=result.status,
                        message=result.message,
                    )
                    for result in res.result.results
                    if result.status in FAILURE_STATUSES
                ]
                raise ValueError(
                    f"Failures detected during invocation of dbt command '{''.join(args)}':\n{os.linesep.join(failure_results)}"
                )
            return res

    def invoke(self, args: list[str], **kwargs: Any):
        """Synchronously invokes a dbt command."""
        context = serialize_context()
        task_state = TaskState()

        related_prefect_context = run_coro_as_sync(
            related_resources_from_run_context(self.client),
        )
        assert related_prefect_context is not None

        invoke_kwargs = {
            "project_dir": kwargs.pop("project_dir", self.settings.project_dir),
            "profiles_dir": kwargs.pop("profiles_dir", self.settings.profiles_dir),
            "log_level": kwargs.pop(
                "log_level",
                "none" if related_prefect_context else self.settings.log_level,
            ),
            **kwargs,
        }

        with resolve_profiles_yml(invoke_kwargs["profiles_dir"]) as profiles_dir:
            invoke_kwargs["profiles_dir"] = profiles_dir

            callbacks = [
                self._create_logging_callback(
                    task_state, self.settings.log_level, context
                ),
                self._create_node_started_callback(task_state, context),
                self._create_node_finished_callback(task_state, context),
            ]
            res = dbtRunner(callbacks=callbacks).invoke(args, **invoke_kwargs)  # type: ignore[reportUnknownMemberType]

            if not res.success and res.exception:
                raise ValueError(
                    f"Failed to invoke dbt command '{''.join(args)}': {res.exception}"
                )
            elif not res.success and self.raise_on_failure:
                assert isinstance(res.result, RunExecutionResult), (
                    "Expected run execution result from failed dbt invoke"
                )
                failure_results = [
                    FAILURE_MSG.format(
                        resource_type=result.node.resource_type.title(),
                        resource_name=result.node.name,
                        status=result.status,
                        message=result.message,
                    )
                    for result in res.result.results
                    if result.status in FAILURE_STATUSES
                ]
                raise ValueError(
                    f"Failures detected during invocation of dbt command '{''.join(args)}':\n{os.linesep.join(failure_results)}"
                )
            return res
