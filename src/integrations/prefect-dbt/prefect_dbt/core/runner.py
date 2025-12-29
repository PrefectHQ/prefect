"""
Runner for dbt commands
"""

import json
import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Union

from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import (
    FreshnessStatus,
    NodeStatus,
    RunStatus,
    TestStatus,
)
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.cli.main import cli, dbtRunner
from dbt.compilation import Linker
from dbt.config.runtime import RuntimeConfig
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode, SourceDefinition
from dbt.contracts.state import (
    load_result_state,  # type: ignore[reportUnknownMemberType]
)
from dbt.graph.graph import Graph, UniqueId
from dbt_common.events.base_types import EventLevel, EventMsg
from google.protobuf.json_format import MessageToDict

from prefect import get_client, get_run_logger
from prefect._internal.uuid7 import uuid7
from prefect.assets import Asset, AssetProperties
from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH
from prefect.cache_policies import NO_CACHE
from prefect.client.orchestration import PrefectClient
from prefect.context import AssetContext, hydrated_context, serialize_context
from prefect.exceptions import MissingContextError
from prefect.tasks import MaterializingTask, Task, TaskOptions
from prefect_dbt.core._tracker import NodeTaskTracker
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import format_resource_id, kwargs_to_args

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
SKIPPED_STATUSES = [
    RunStatus.Skipped,
    TestStatus.Skipped,
    NodeStatus.Skipped,
]
MATERIALIZATION_NODE_TYPES = [
    NodeType.Model,
    NodeType.Seed,
    NodeType.Snapshot,
]
REFERENCE_NODE_TYPES = [
    NodeType.Exposure,
    NodeType.Source,
]

SETTINGS_CONFIG = [
    ("target_path", "--target-path", Path),
    ("profiles_dir", "--profiles-dir", Path),
    ("project_dir", "--project-dir", Path),
    ("log_level", "--log-level", EventLevel),
]
FAILURE_MSG = '{resource_type} {resource_name} {status}ed with message: "{message}"'


def execute_dbt_node(
    task_state: NodeTaskTracker, node_id: str, asset_id: Union[str, None]
):
    """Execute a dbt node and wait for its completion.

    This function will:
    1. Set up the task logger
    2. Wait for the node to finish using efficient threading.Event
    3. Check the node's status and fail if it's in a failure state
    """
    # Wait for the node to finish using efficient threading.Event
    task_state.wait_for_node_completion(node_id)

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

    This class enables the invocation of dbt commands while integrating with Prefect's
    logging and assets capabilities.

    Args:
        manifest: Optional pre-loaded dbt manifest
        settings: Optional PrefectDbtSettings instance for configuring dbt
        raise_on_failure: Whether to raise an error if the dbt command encounters a
            non-exception failure
        client: Optional Prefect client instance
        include_compiled_code: Whether to include compiled code in the asset description
        disable_assets: Global override for disabling asset generation for dbt nodes. If
            True, assets will not be created for any dbt nodes, even if the node's prefect
            config has enable_assets set to True.
        _force_nodes_as_tasks: Whether to force each dbt node execution to have a Prefect task
            representation when `.invoke()` is called outside of a flow or task run
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        settings: Optional[PrefectDbtSettings] = None,
        raise_on_failure: bool = True,
        client: Optional[PrefectClient] = None,
        include_compiled_code: bool = False,
        disable_assets: bool = False,
        _force_nodes_as_tasks: bool = False,
        _disable_callbacks: bool = False,
    ):
        self._manifest: Optional[Manifest] = manifest
        self.settings = settings or PrefectDbtSettings()
        self.raise_on_failure = raise_on_failure
        self.client = client or get_client()
        self.include_compiled_code = include_compiled_code
        self.disable_assets = disable_assets
        self._force_nodes_as_tasks = _force_nodes_as_tasks
        self._disable_callbacks = _disable_callbacks
        self._project_name: Optional[str] = None
        self._target_path: Optional[Path] = None
        self._profiles_dir: Optional[Path] = None
        self._project_dir: Optional[Path] = None
        self._log_level: Optional[EventLevel] = None
        self._config: Optional[RuntimeConfig] = None
        self._graph: Optional[Graph] = None
        self._skipped_nodes: set[str] = set()

        self._event_queue: Optional[queue.PriorityQueue] = None
        self._callback_thread: Optional[threading.Thread] = None
        self._shutdown_event: Optional[threading.Event] = None
        self._queue_counter = 0  # Counter for tiebreaking in PriorityQueue
        self._queue_counter_lock = threading.Lock()  # Thread-safe counter increment

    @property
    def target_path(self) -> Path:
        return self._target_path or self.settings.target_path

    @property
    def profiles_dir(self) -> Path:
        return self._profiles_dir or self.settings.profiles_dir

    @property
    def project_dir(self) -> Path:
        return self._project_dir or self.settings.project_dir

    @property
    def log_level(self) -> EventLevel:
        return self._log_level or self.settings.log_level

    @property
    def manifest(self) -> Manifest:
        if self._manifest is None:
            self._set_manifest_from_project_dir()
            assert self._manifest is not None  # for type checking
        return self._manifest

    @property
    def graph(self) -> Graph:
        if self._graph is None:
            self._set_graph_from_manifest()
            assert self._graph is not None
        return self._graph

    @property
    def project_name(self) -> str:
        if self._project_name is None:
            self._set_project_name_from_manifest()
            assert self._project_name is not None
        return self._project_name

    def _set_project_name_from_manifest(self) -> Optional[str]:
        self._project_name = self.manifest.metadata.project_name

    def _set_graph_from_manifest(self, add_test_edges: bool = False):
        linker = Linker()
        linker.link_graph(self.manifest)
        if add_test_edges:
            self.manifest.build_parent_and_child_maps()
            linker.add_test_edges(self.manifest)
        self._graph = Graph(linker.graph)

    def _set_manifest_from_project_dir(self):
        try:
            with open(
                os.path.join(self.project_dir, self.target_path, "manifest.json"), "r"
            ) as f:
                self._manifest = Manifest.from_dict(json.load(f))  # type: ignore[reportUnknownMemberType]
        except FileNotFoundError:
            raise ValueError(
                f"Manifest file not found in {os.path.join(self.project_dir, self.target_path, 'manifest.json')}"
            )

    def _get_node_prefect_config(
        self, manifest_node: Union[ManifestNode, SourceDefinition]
    ) -> dict[str, dict[str, Any]]:
        if isinstance(manifest_node, SourceDefinition):
            return manifest_node.meta.get("prefect", {})

        return manifest_node.config.meta.get("prefect", {})

    def _get_upstream_manifest_nodes_and_configs(
        self,
        manifest_node: ManifestNode,
    ) -> list[tuple[Union[ManifestNode, SourceDefinition], dict[str, Any]]]:
        """
        Get upstream nodes for a given node.
        Ephemeral nodes are traversed recursively to find non-ephemeral dependencies.
        Sources without relation_name are ignored.
        """
        upstream_manifest_nodes: list[
            tuple[Union[ManifestNode, SourceDefinition], dict[str, Any]]
        ] = []
        visited: set[str] = set()

        def collect(node: ManifestNode | SourceDefinition):
            for depends_on_node in node.depends_on_nodes:  # type: ignore[reportUnknownMemberType]
                if depends_on_node in visited:
                    continue
                visited.add(depends_on_node)

                depends_manifest_node = (
                    self.manifest.nodes.get(depends_on_node)  # type: ignore[reportUnknownMemberType]
                    or self.manifest.sources.get(depends_on_node)  # type: ignore[reportUnknownMemberType]
                )

                if not depends_manifest_node:
                    continue

                # sources without relation_name
                if (
                    depends_on_node in self.manifest.sources
                    and not depends_manifest_node.relation_name
                ):
                    continue

                # recursive for ephemerals
                if (
                    depends_on_node in self.manifest.nodes
                    and depends_manifest_node.config.materialized == "ephemeral"
                ):
                    collect(depends_manifest_node)
                    continue

                upstream_manifest_nodes.append(
                    (
                        depends_manifest_node,
                        self._get_node_prefect_config(depends_manifest_node),
                    )
                )

        collect(manifest_node)
        return upstream_manifest_nodes

    def _get_compiled_code_path(self, manifest_node: ManifestNode) -> Path:
        """Get the path to compiled code for a manifest node."""
        return (
            Path(self.project_dir)
            / self.target_path
            / "compiled"
            / self.project_name
            / manifest_node.original_file_path
        )

    def _get_compiled_code(
        self, manifest_node: Union[ManifestNode, SourceDefinition]
    ) -> str:
        """Get compiled code for a manifest node if it exists and is enabled."""
        if not self.include_compiled_code or isinstance(
            manifest_node, SourceDefinition
        ):
            return ""

        compiled_code_path = self._get_compiled_code_path(manifest_node)
        if os.path.exists(compiled_code_path):
            with open(compiled_code_path, "r") as f:
                code_content = f.read()
                description = (
                    f"\n ### Compiled code\n```sql\n{code_content.strip()}\n```"
                )

            if len(description) > MAX_ASSET_DESCRIPTION_LENGTH:
                warning_msg = (
                    f"Compiled code for {manifest_node.name} was omitted because it exceeded the "
                    f"maximum asset description length of {MAX_ASSET_DESCRIPTION_LENGTH} characters."
                )
                description = "\n ### Compiled code\n" + warning_msg
                try:
                    logger = get_run_logger()
                    logger.warning(warning_msg)
                except MissingContextError:
                    pass

            return description

        return ""

    def _create_asset_from_node(
        self, manifest_node: Union[ManifestNode, SourceDefinition], adapter_type: str
    ) -> Asset:
        """Create an Asset from a manifest node."""
        if not manifest_node.relation_name:
            raise ValueError("Relation name not found in manifest")

        asset_id = format_resource_id(adapter_type, manifest_node.relation_name)
        compiled_code = self._get_compiled_code(manifest_node)

        if isinstance(manifest_node, SourceDefinition):
            owner = manifest_node.meta.get("owner")
        else:
            owner = manifest_node.config.meta.get("owner")

        if owner and isinstance(owner, str):
            owners = [owner]
        else:
            owners = None

        return Asset(
            key=asset_id,
            properties=AssetProperties(
                name=manifest_node.name,
                description=manifest_node.description + compiled_code,
                owners=owners,
            ),
        )

    def _create_task_options(
        self, manifest_node: ManifestNode, upstream_assets: Optional[list[Asset]] = None
    ) -> TaskOptions:
        """Create TaskOptions for a manifest node."""
        return TaskOptions(
            task_run_name=f"{manifest_node.resource_type.lower()} {manifest_node.name if manifest_node.name else manifest_node.unique_id}",
            asset_deps=upstream_assets,  # type: ignore[arg-type]
            cache_policy=NO_CACHE,
        )

    def _get_manifest_node_and_config(
        self, node_id: str
    ) -> tuple[Optional[ManifestNode], dict[str, Any]]:
        """Get manifest node and its prefect config."""
        manifest_node = self.manifest.nodes.get(node_id)
        if manifest_node:
            prefect_config = manifest_node.config.meta.get("prefect", {})
            return manifest_node, prefect_config
        return None, {}

    def _call_task(
        self,
        task_state: NodeTaskTracker,
        manifest_node: ManifestNode,
        context: dict[str, Any],
        enable_assets: bool,
    ):
        """Create and run a task for a node."""
        adapter_type = self.manifest.metadata.adapter_type
        if not adapter_type:
            raise ValueError("Adapter type not found in manifest")

        upstream_manifest_nodes = self._get_upstream_manifest_nodes_and_configs(
            manifest_node
        )

        # Only create assets for materialization nodes that have a relation_name.
        # Ephemeral models are NodeType.Model but have relation_name=None because
        # they're CTEs that don't create database objects. We skip asset creation
        # for these and fall through to create a regular Task instead.
        # See: https://github.com/PrefectHQ/prefect/issues/19821
        if (
            manifest_node.resource_type in MATERIALIZATION_NODE_TYPES
            and enable_assets
            and manifest_node.relation_name
        ):
            asset = self._create_asset_from_node(manifest_node, adapter_type)

            upstream_assets: list[Asset] = []
            for (
                upstream_manifest_node,
                upstream_manifest_node_config,
            ) in upstream_manifest_nodes:
                if (
                    upstream_manifest_node.resource_type in REFERENCE_NODE_TYPES
                    or upstream_manifest_node.resource_type
                    in MATERIALIZATION_NODE_TYPES
                    and upstream_manifest_node_config.get("enable_assets", True)
                ):
                    upstream_asset = self._create_asset_from_node(
                        upstream_manifest_node, adapter_type
                    )
                    upstream_assets.append(upstream_asset)

            task_options = self._create_task_options(manifest_node, upstream_assets)
            asset_id = format_resource_id(adapter_type, manifest_node.relation_name)

            task = MaterializingTask(
                fn=execute_dbt_node,
                assets=[asset],
                materialized_by="dbt",
                **task_options,
            )

        else:
            asset_id = None
            task_options = self._create_task_options(manifest_node)
            task = Task(
                fn=execute_dbt_node,
                **task_options,
            )

        # Start the task in a separate thread
        task_state.start_task(manifest_node.unique_id, task)

        task_state.set_node_dependencies(
            manifest_node.unique_id,
            [node[0].unique_id for node in upstream_manifest_nodes],
        )

        task_run_id = uuid7()

        task_state.set_task_run_id(manifest_node.unique_id, task_run_id)

        task_state.run_task_in_thread(
            manifest_node.unique_id,
            task,
            task_run_id=task_run_id,
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

    def _get_dbt_event_node_id(self, event: EventMsg) -> str:
        return event.data.node_info.unique_id  # type: ignore[reportUnknownMemberType]

    def _start_callback_processor(self) -> None:
        """Start the background thread for processing callbacks."""
        if self._event_queue is None:
            # Use PriorityQueue to ensure NodeStart events are processed first
            # Priority: 0 = NodeStart (highest), 1 = NodeFinished, 2 = everything else (lowest)
            self._event_queue = queue.PriorityQueue(maxsize=0)
            self._shutdown_event = threading.Event()
            self._callback_thread = threading.Thread(
                target=self._callback_worker, daemon=True, name="dbt-callback-processor"
            )
            self._callback_thread.start()

    def _stop_callback_processor(self) -> None:
        """Stop the background thread and wait for queue to drain."""
        if self._shutdown_event:
            self._shutdown_event.set()
        if self._event_queue:
            # Put a sentinel to wake up the worker (with highest priority to ensure it's processed)
            try:
                # Use counter -1 to ensure sentinel is processed first among priority 0 items
                with self._queue_counter_lock:
                    sentinel_counter = self._queue_counter - 1
                self._event_queue.put(
                    (0, sentinel_counter, None), timeout=0.1
                )  # Priority 0 to process immediately
            except queue.Full:
                pass
        if self._callback_thread and self._callback_thread.is_alive():
            self._callback_thread.join(timeout=5.0)

        # Reset state so next invoke() can create a fresh callback processor
        self._event_queue = None
        self._callback_thread = None
        self._shutdown_event = None
        self._queue_counter = 0
        self._skipped_nodes = set()

    def _callback_worker(self) -> None:
        """Background worker thread that processes queued events."""
        while not self._shutdown_event.is_set():
            event_data = None
            item_retrieved = False
            try:
                # Get event with timeout to periodically check shutdown
                # PriorityQueue returns (priority, counter, item) tuples
                _, _, event_data = self._event_queue.get(timeout=0.1)
                item_retrieved = True
                if event_data is None:  # Sentinel to shutdown
                    break

                callback_func, event_msg = event_data
                callback_func(event_msg)

            except queue.Empty:
                continue
            finally:
                # Always call task_done() exactly once per successfully retrieved item
                # This includes the None sentinel used for shutdown
                if item_retrieved:
                    self._event_queue.task_done()

    def _get_event_priority(self, event: EventMsg) -> int:
        """Get priority for an event. Lower number = higher priority.

        Priority levels:
        - 0: NodeStart (highest - must create tasks before other events)
        - 1: NodeFinished (medium - update task status)
        - 2: Everything else (lowest - logging, etc.)
        """
        event_name = event.info.name
        if event_name == "NodeStart":
            return 0
        elif event_name == "NodeFinished":
            return 1
        else:
            return 2

    def _queue_callback(
        self,
        callback_func: Callable[[EventMsg], None],
        event: EventMsg,
        priority: Optional[int] = None,
    ) -> None:
        """Helper method to queue a callback for background processing.

        Args:
            callback_func: The callback function to execute
            event: The event message
            priority: Optional priority override. If None, determined from event name.
        """
        if self._event_queue is None:
            # Fallback to synchronous if queue not initialized
            callback_func(event)
            return

        # Determine priority if not provided
        if priority is None:
            priority = self._get_event_priority(event)

        # Get a unique counter value for tiebreaking (ensures items with same priority
        # can be ordered without comparing EventMsg objects)
        with self._queue_counter_lock:
            counter = self._queue_counter
            self._queue_counter += 1

        # Queue the callback for background processing (non-blocking)
        try:
            self._event_queue.put(
                (priority, counter, (callback_func, event)), block=False
            )
        except queue.Full:
            # If queue is full, fall back to synchronous processing
            # This prevents blocking dbt but may slow it down
            callback_func(event)

    def _create_unified_callback(
        self,
        task_state: NodeTaskTracker,
        log_level: EventLevel,
        context: dict[str, Any],
        add_test_edges: bool = False,
    ) -> Callable[[EventMsg], None]:
        """Creates a single unified callback that efficiently filters and routes dbt events.

        This approach optimizes performance by:
        1. Using a dictionary dispatch table for O(1) routing (faster than if/elif chains)
        2. Minimizing attribute access by caching event.info.name once
        3. Using set membership checks for the most common case (logging events)
        4. Only ONE callback registered with dbtRunner

        Note: While we cannot avoid the function call overhead entirely (dbt's API limitation),
        this implementation minimizes the work done per event to the absolute minimum.
        """

        # Start the callback processor if not already started
        self._start_callback_processor()

        # Pre-compute event name constants (for use in dispatch table)
        _NODE_START = "NodeStart"
        _NODE_FINISHED = "NodeFinished"

        def _process_logging_sync(event: EventMsg) -> None:
            """Actual logging logic - runs in background thread."""
            event_data = MessageToDict(event.data, preserving_proto_field_name=True)

            # Handle logging for all events with node_info
            if event_data.get("node_info"):
                node_id = self._get_dbt_event_node_id(event)

                # Skip logging for skipped nodes
                if node_id not in self._skipped_nodes:
                    flow_run_context: Optional[dict[str, Any]] = context.get(
                        "flow_run_context"
                    )
                    logger = task_state.get_task_logger(
                        node_id,
                        flow_run_context.get("flow_run") if flow_run_context else None,
                        flow_run_context.get("flow") if flow_run_context else None,
                    )
                else:
                    logger = None
            else:
                # Get logger for events without node_info
                try:
                    with hydrated_context(context) as run_context:
                        logger = get_run_logger(run_context)
                except MissingContextError:
                    logger = None

            # Log the event if logger is available
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

        def _process_node_started_sync(event: EventMsg) -> None:
            """
            Actual node started logic - runs in background thread.
            Skips nodes that are ephemeral.
            """
            node_id = self._get_dbt_event_node_id(event)
            if node_id in self._skipped_nodes:
                return

            manifest_node, prefect_config = self._get_manifest_node_and_config(node_id)

            if not manifest_node:
                return

            if manifest_node.config.materialized == "ephemeral":
                self._skipped_nodes.add(node_id)
                return

            enable_assets = (
                prefect_config.get("enable_assets", True) and not self.disable_assets
            )
            self._call_task(task_state, manifest_node, context, enable_assets)

        def _process_node_finished_sync(event: EventMsg) -> None:
            """Actual node finished logic - runs in background thread."""
            node_id = self._get_dbt_event_node_id(event)
            if node_id in self._skipped_nodes:
                return

            manifest_node, _ = self._get_manifest_node_and_config(node_id)

            if manifest_node:
                event_data = MessageToDict(event.data, preserving_proto_field_name=True)
                # Store the status before ending the task
                event_message = self.get_dbt_event_msg(event)
                task_state.set_node_status(node_id, event_data, event_message)

                node_info: Optional[dict[str, Any]] = event_data.get("node_info")
                node_status: Optional[str] = (
                    node_info.get("node_status") if node_info else None
                )

                if node_status in SKIPPED_STATUSES or node_status in FAILURE_STATUSES:
                    self._set_graph_from_manifest(add_test_edges=add_test_edges)
                    for dep_node_id in self.graph.get_dependent_nodes(  # type: ignore[reportUnknownMemberType]
                        UniqueId(node_id)
                    ):  # type: ignore[reportUnknownMemberType]
                        self._skipped_nodes.add(dep_node_id)  # type: ignore[reportUnknownMemberType]

        # Create dispatch table for O(1) routing (faster than if/elif for >2 branches)
        # Using a tuple of (handler, priority) for efficient dispatch
        # None value means use default logging handler
        _EVENT_DISPATCH = {
            _NODE_START: (_process_node_started_sync, 0),
            _NODE_FINISHED: (_process_node_finished_sync, 1),
        }

        # Create a mapping of EventLevel to numeric priority for fast comparison
        # Higher numbers = higher priority (more important, less verbose)
        # DEBUG (0) is most verbose, ERROR (4) is most important
        _EVENT_LEVEL_PRIORITY = {
            EventLevel.DEBUG: 0,
            EventLevel.TEST: 1,
            EventLevel.INFO: 2,
            EventLevel.WARN: 3,
            EventLevel.ERROR: 4,
        }

        # Get the minimum priority level we should log
        # If log_level is INFO (2), we log INFO (2), WARN (3), ERROR (4)
        # If log_level is WARN (3), we log WARN (3), ERROR (4)
        _min_log_priority = _EVENT_LEVEL_PRIORITY.get(log_level, 2)  # Default to INFO

        def unified_callback(event: EventMsg) -> None:
            """Ultra-efficient callback that minimizes work per event.

            Optimization strategy:
            1. Route critical events (NodeStart/NodeFinished) immediately
            2. For logging events, apply early filtering BEFORE queuing:
               - Filter by log level (don't queue events below threshold)
               - Filter out events without messages
               - This dramatically reduces queue operations for irrelevant events
            3. Single attribute access cached in local variable
            4. Dictionary lookup for routing (O(1))

            This is the most efficient possible implementation given dbt's callback API
            limitations. We cannot avoid the function call, but we minimize all other work.

            Performance notes:
            - Early filtering prevents queuing ~70-90% of events that would never be logged
            - Dictionary .get() is O(1) and faster than 'in' check + separate lookup
            - Only events that will actually be logged are queued
            """
            # Single attribute access - cache it to avoid repeated lookups
            event_name = event.info.name

            # Single dictionary lookup handles both existence check and routing
            # Returns None for events not in dispatch table (fast path for logging)
            dispatch_result = _EVENT_DISPATCH.get(event_name)

            if dispatch_result is not None:
                # Critical event (NodeStart/NodeFinished) - always process
                handler, priority = dispatch_result
                self._queue_callback(handler, event, priority=priority)
            else:
                # Potential logging event - apply early filtering
                # Check log level first (cheap attribute access)
                event_level = event.info.level
                event_priority = _EVENT_LEVEL_PRIORITY.get(event_level, -1)

                # Skip events below our log level threshold
                # If log_level is INFO (2), skip DEBUG (0) and TEST (1)
                # If log_level is WARN (3), skip DEBUG (0), TEST (1), INFO (2)
                if event_priority < _min_log_priority:
                    return  # Don't queue - won't be logged anyway

                # Check if event has a message (cheap attribute access)
                # Some events might not have messages, so we skip those
                try:
                    event_msg = event.info.msg  # type: ignore[reportUnknownMemberType]
                    # Skip events without messages or with empty/whitespace-only messages
                    if not event_msg:
                        return  # No message - don't queue
                    # Only do string operation if message exists (most events have messages)
                    if isinstance(event_msg, str) and not event_msg.strip():
                        return  # Whitespace-only message - don't queue
                except (AttributeError, TypeError):
                    return  # No message attribute - don't queue

                # Event passed all filters - queue for logging
                self._queue_callback(_process_logging_sync, event)

        return unified_callback

    def _create_logging_callback(
        self,
        task_state: NodeTaskTracker,
        log_level: EventLevel,
        context: dict[str, Any],
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for logging dbt events.

        DEPRECATED: This method is kept for backward compatibility but is no longer
        used. Use _create_unified_callback instead for better performance.
        """
        # Start the callback processor if not already started
        self._start_callback_processor()

        def _process_logging_sync(event: EventMsg) -> None:
            """Actual logging logic - runs in background thread."""
            # Skip logging for NodeStart and NodeFinished events - they have their own callbacks
            if event.info.name in ("NodeStart", "NodeFinished"):
                return

            event_data = MessageToDict(event.data, preserving_proto_field_name=True)

            # Handle logging for all events with node_info
            if event_data.get("node_info"):
                node_id = self._get_dbt_event_node_id(event)

                # Skip logging for skipped nodes
                if node_id not in self._skipped_nodes:
                    flow_run_context: Optional[dict[str, Any]] = context.get(
                        "flow_run_context"
                    )
                    logger = task_state.get_task_logger(
                        node_id,
                        flow_run_context.get("flow_run") if flow_run_context else None,
                        flow_run_context.get("flow") if flow_run_context else None,
                    )
                else:
                    logger = None
            else:
                # Get logger for events without node_info
                try:
                    with hydrated_context(context) as run_context:
                        logger = get_run_logger(run_context)
                except MissingContextError:
                    logger = None

            # Log the event if logger is available
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

        def logging_callback(event: EventMsg) -> None:
            """Non-blocking callback wrapper that queues logging for background processing."""
            # Early filter: Skip NodeStart and NodeFinished events - they have their own callbacks
            if event.info.name in ("NodeStart", "NodeFinished"):
                return

            # Only queue events that will actually be processed
            self._queue_callback(_process_logging_sync, event)

        return logging_callback

    def _create_node_started_callback(
        self, task_state: NodeTaskTracker, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for starting tasks when nodes start.

        DEPRECATED: This method is kept for backward compatibility but is no longer
        used. Use _create_unified_callback instead for better performance.
        """
        # Start the callback processor if not already started
        self._start_callback_processor()

        def _process_node_started_sync(event: EventMsg) -> None:
            """Actual node started logic - runs in background thread."""
            if event.info.name == "NodeStart":
                node_id = self._get_dbt_event_node_id(event)
                if node_id in self._skipped_nodes:
                    return

                manifest_node, prefect_config = self._get_manifest_node_and_config(
                    node_id
                )

                if manifest_node:
                    enable_assets = (
                        prefect_config.get("enable_assets", True)
                        and not self.disable_assets
                    )
                    self._call_task(task_state, manifest_node, context, enable_assets)

        def node_started_callback(event: EventMsg) -> None:
            """Non-blocking callback wrapper that queues node started processing.

            NodeStart events are queued with highest priority (0) to ensure
            tasks are created before other events for the same node are processed.
            """
            # Early filter: Only process NodeStart events
            if event.info.name != "NodeStart":
                return

            # Queue with highest priority to process before other events
            self._queue_callback(_process_node_started_sync, event, priority=0)

        return node_started_callback

    def _create_node_finished_callback(
        self,
        task_state: NodeTaskTracker,
        context: dict[str, Any],
        add_test_edges: bool = False,
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for ending tasks when nodes finish.

        DEPRECATED: This method is kept for backward compatibility but is no longer
        used. Use _create_unified_callback instead for better performance.
        """
        # Start the callback processor if not already started
        self._start_callback_processor()

        def _process_node_finished_sync(event: EventMsg) -> None:
            """Actual node finished logic - runs in background thread."""
            if event.info.name == "NodeFinished":
                node_id = self._get_dbt_event_node_id(event)
                if node_id in self._skipped_nodes:
                    return

                manifest_node, _ = self._get_manifest_node_and_config(node_id)

                if manifest_node:
                    event_data = MessageToDict(
                        event.data, preserving_proto_field_name=True
                    )
                    # Store the status before ending the task
                    event_message = self.get_dbt_event_msg(event)
                    task_state.set_node_status(node_id, event_data, event_message)

                    node_info: Optional[dict[str, Any]] = event_data.get("node_info")
                    node_status: Optional[str] = (
                        node_info.get("node_status") if node_info else None
                    )

                    if (
                        node_status in SKIPPED_STATUSES
                        or node_status in FAILURE_STATUSES
                    ):
                        self._set_graph_from_manifest(add_test_edges=add_test_edges)
                        for dep_node_id in self.graph.get_dependent_nodes(  # type: ignore[reportUnknownMemberType]
                            UniqueId(node_id)
                        ):  # type: ignore[reportUnknownMemberType]
                            self._skipped_nodes.add(dep_node_id)  # type: ignore[reportUnknownMemberType]

        def node_finished_callback(event: EventMsg) -> None:
            """Non-blocking callback wrapper that queues node finished processing.

            NodeFinished events are queued with medium priority (1) to ensure
            they're processed after NodeStart but before regular logging events.
            """
            # Early filter: Only process NodeFinished events
            if event.info.name != "NodeFinished":
                return

            # Queue with medium priority (automatically set by _queue_callback)
            self._queue_callback(_process_node_finished_sync, event, priority=1)

        return node_finished_callback

    def _extract_flag_value(
        self, args: list[str], flag: str
    ) -> tuple[list[str], Union[str, None]]:
        """
        Extract a flag value from args and return the modified args and the value.

        Args:
            args: List of command line arguments
            flag: The flag to look for (e.g., "--target-path")

        Returns:
            Tuple of (modified_args, flag_value)
        """
        args_copy = args.copy()
        for i, arg in enumerate(args_copy):
            if arg == flag and i + 1 < len(args_copy):
                value = args_copy[i + 1]
                args_copy.pop(i)  # Remove the flag
                args_copy.pop(i)  # Remove the value
                return args_copy, value
        return args_copy, None

    def _update_setting_from_kwargs(
        self,
        setting_name: str,
        kwargs: dict[str, Any],
        path_converter: Optional[Callable[[Any], Any]] = None,
    ):
        """Update a setting from kwargs if present."""
        if setting_name in kwargs:
            value = kwargs.pop(setting_name)
            if path_converter:
                value = path_converter(value)
            setattr(self, f"_{setting_name}", value)

    def _update_setting_from_cli_flag(
        self,
        args: list[str],
        flag: str,
        setting_name: str,
        path_converter: Optional[Callable[[str], Any]] = None,
    ) -> list[str]:
        """Update a setting from CLI flag if present."""
        args_copy, value = self._extract_flag_value(args, flag)
        if value and path_converter:
            setattr(self, f"_{setting_name}", path_converter(value))
        return args_copy

    def invoke(self, args: list[str], **kwargs: Any):
        """
        Invokes a dbt command.

        Supports the same arguments as `dbtRunner.invoke()`. https://docs.getdbt.com/reference/programmatic-invocations

        Args:
            args: List of command line arguments
            **kwargs: Additional keyword arguments

        Returns:
            The result of the dbt command invocation
        """
        # Handle kwargs for each setting
        for setting_name, _, converter in SETTINGS_CONFIG:
            self._update_setting_from_kwargs(setting_name, kwargs, converter)

        # Handle CLI flags for each setting
        args_copy = args.copy()
        for setting_name, flag, converter in SETTINGS_CONFIG:
            args_copy = self._update_setting_from_cli_flag(
                args_copy, flag, setting_name, converter
            )

        context = serialize_context()
        in_flow_or_task_run = context.get("flow_run_context") or context.get(
            "task_run_context"
        )
        task_state = NodeTaskTracker()

        add_test_edges = True if "build" in args_copy else False

        if "retry" in args_copy:
            previous_results = load_result_state(
                Path(self.project_dir) / self.target_path / "run_results.json"
            )
            if not previous_results:
                raise ValueError(
                    f"Cannot retry. No previous results found at target path {self.target_path}"
                )
            previous_args = previous_results.args
            self.previous_command_name = previous_args.get("which")
            if self.previous_command_name == "build":
                add_test_edges = True

        if not self._disable_callbacks:
            callbacks = (
                [
                    self._create_unified_callback(
                        task_state,
                        self.log_level,
                        context,
                        add_test_edges=add_test_edges,
                    ),
                ]
                if in_flow_or_task_run or self._force_nodes_as_tasks
                else []
            )
        else:
            callbacks = []

        # Determine which command is being invoked
        # We need to find a valid dbt command, skipping flag values like "json" in "--log-format json"
        command_name = None
        for arg in args_copy:
            if arg.startswith("-"):
                continue
            # Check if this is a valid dbt command
            if arg in cli.commands:
                command_name = arg
                break

        # Build invoke_kwargs with only parameters valid for this command
        invoke_kwargs = {}

        # Get valid parameters for the command if we can determine it
        valid_params = None
        if command_name:
            command = cli.commands.get(command_name)
            if command:
                valid_params = {p.name for p in command.params}

        # Add settings to kwargs only if they're valid for the command
        potential_kwargs = {
            "profiles_dir": str(self.profiles_dir),
            "project_dir": str(self.project_dir),
            "target_path": str(self.target_path),
            "log_level": "none" if in_flow_or_task_run else str(self.log_level.value),
            "log_level_file": str(self.log_level.value),
        }

        for key, value in potential_kwargs.items():
            # If we couldn't determine valid params, include all (backward compat)
            # Otherwise only include if it's valid for this command
            if valid_params is None or key in valid_params:
                invoke_kwargs[key] = value

        # Add any additional kwargs passed by the user
        invoke_kwargs.update(kwargs)

        with self.settings.resolve_profiles_yml() as profiles_dir:
            invoke_kwargs["profiles_dir"] = profiles_dir

            res = dbtRunner(callbacks=callbacks).invoke(  # type: ignore[reportUnknownMemberType]
                kwargs_to_args(invoke_kwargs, args_copy)
            )

        # Wait for callback queue to drain after dbt execution completes
        # Since dbt execution is complete, no new events will be added.
        # Wait for the background worker to process all remaining items.
        if self._event_queue is not None:
            self._event_queue.join()
            # Stop the callback processor now that all items are processed
            self._stop_callback_processor()

        if not res.success and res.exception:
            raise ValueError(
                f"Failed to invoke dbt command '{''.join(args_copy)}': {res.exception}"
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
                f"Failures detected during invocation of dbt command '{' '.join(args_copy)}':\n{os.linesep.join(failure_results)}"
            )
        return res
