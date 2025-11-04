"""
Runner for dbt commands
"""

import json
import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Union
from uuid import UUID

from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import (
    FreshnessStatus,
    NodeStatus,
    RunStatus,
    TestStatus,
)
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.cli.main import dbtRunner
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

import logging
import time

from prefect import get_client, get_run_logger
from prefect._internal.uuid7 import uuid7
from prefect.assets import Asset, AssetProperties
from prefect.assets.core import MAX_ASSET_DESCRIPTION_LENGTH
from prefect.cache_policies import NO_CACHE
from prefect.client.orchestration import SyncPrefectClient
from prefect.client.schemas.actions import LogCreate
from prefect.context import AssetContext, hydrated_context, serialize_context
from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger
from prefect.tasks import MaterializingTask, Task, TaskOptions
from prefect.types._datetime import from_timestamp
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
        callback_workers: Number of worker threads to use for processing dbt callbacks in parallel.
            Defaults to 4. Increasing this can reduce the delay in reporting to Prefect when processing
            thousands of dbt events, but uses more system resources.
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        settings: Optional[PrefectDbtSettings] = None,
        raise_on_failure: bool = True,
        client: Optional[SyncPrefectClient] = None,
        include_compiled_code: bool = False,
        disable_assets: bool = False,
        _force_nodes_as_tasks: bool = False,
        callback_workers: int = 4,
    ):
        self._manifest: Optional[Manifest] = manifest
        self.settings = settings or PrefectDbtSettings()
        self.raise_on_failure = raise_on_failure
        self.client = client or get_client(sync_client=True)
        self.include_compiled_code = include_compiled_code
        self.disable_assets = disable_assets
        self._force_nodes_as_tasks = _force_nodes_as_tasks

        self._project_name: Optional[str] = None
        self._target_path: Optional[Path] = None
        self._profiles_dir: Optional[Path] = None
        self._project_dir: Optional[Path] = None
        self._log_level: Optional[EventLevel] = None
        self._config: Optional[RuntimeConfig] = None
        self._graph: Optional[Graph] = None
        self._skipped_nodes: set[str] = set()
        
        self._event_queue: Optional[queue.PriorityQueue] = None
        self._callback_threads: list[threading.Thread] = []
        self._shutdown_event: Optional[threading.Event] = None
        self._queue_counter = 0  # Counter for tiebreaking in PriorityQueue
        self._queue_counter_lock = threading.Lock()  # Thread-safe counter increment
        self._num_workers = max(4, callback_workers)  # Number of worker threads for parallel processing
        
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
        """Get upstream nodes for a given node"""
        upstream_manifest_nodes: list[
            tuple[Union[ManifestNode, SourceDefinition], dict[str, Any]]
        ] = []

        for depends_on_node in manifest_node.depends_on_nodes:  # type: ignore[reportUnknownMemberType]
            depends_manifest_node = self.manifest.nodes.get(
                depends_on_node  # type: ignore[reportUnknownMemberType]
            ) or self.manifest.sources.get(depends_on_node)  # type: ignore[reportUnknownMemberType]

            if not depends_manifest_node:
                continue

            if not depends_manifest_node.relation_name:
                raise ValueError("Relation name not found in manifest")

            upstream_manifest_nodes.append(
                (
                    depends_manifest_node,
                    self._get_node_prefect_config(depends_manifest_node),
                )
            )

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

        if manifest_node.resource_type in MATERIALIZATION_NODE_TYPES and enable_assets:
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
            if not manifest_node.relation_name:
                raise ValueError("Relation name not found in manifest")
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

    @staticmethod
    def _extract_event_timestamp(event: EventMsg) -> Optional[float]:
        """Extract timestamp from any dbt event (NodeStart, NodeFinished, or logging events).
        
        Attempts to extract the timestamp from various locations in the event structure:
        1. event.info.ts (primary location for dbt event timestamps)
        2. event.data (if timestamp is embedded in event data)
        3. Returns None if no timestamp can be found
        
        Args:
            event: The dbt EventMsg to extract timestamp from
            
        Returns:
            Timestamp as float (seconds since epoch) or None if not available
        """
        # Try event.info.ts first (primary location)
        try:
            if hasattr(event.info, 'ts') and event.info.ts is not None:
                timestamp = event.info.ts  # type: ignore[reportUnknownMemberType]
                if timestamp is not None:
                    return float(timestamp)
        except (AttributeError, TypeError, ValueError):
            pass
        
        # Try to extract from event data if available
        try:
            event_data = MessageToDict(event.data, preserving_proto_field_name=True)
            # Check various possible timestamp fields in event data
            for field in ['ts', 'timestamp', 'created_at', 'occurred_at']:
                if field in event_data and event_data[field] is not None:
                    try:
                        return float(event_data[field])
                    except (TypeError, ValueError):
                        continue
            
            # Check nested locations (e.g., node_info)
            if 'node_info' in event_data and isinstance(event_data['node_info'], dict):
                node_info = event_data['node_info']
                for field in ['ts', 'timestamp', 'created_at', 'occurred_at']:
                    if field in node_info and node_info[field] is not None:
                        try:
                            return float(node_info[field])
                        except (TypeError, ValueError):
                            continue
        except (AttributeError, TypeError, ValueError):
            pass
        
        return None

    def _start_callback_processor(self) -> None:
        """Start the background worker threads for processing callbacks.
        
        Uses multiple worker threads to process events in parallel, significantly
        reducing the time to drain the queue and report to Prefect in real-time.
        """
        if self._event_queue is None:
            # Use PriorityQueue to ensure NodeStart events are processed first
            # Priority: 0 = NodeStart (highest), 1 = NodeFinished, 2 = everything else (lowest)
            self._event_queue = queue.PriorityQueue(maxsize=0)
            self._shutdown_event = threading.Event()
            
            # Start multiple worker threads for parallel processing
            # This allows us to process the queue much faster while dbt is running
            self._callback_threads = []
            for i in range(self._num_workers):
                thread = threading.Thread(
                    target=self._callback_worker,
                    daemon=True,
                    name=f"dbt-callback-processor-{i}"
                )
                thread.start()
                self._callback_threads.append(thread)
    
    def _stop_callback_processor(self) -> None:
        """Stop all background worker threads and wait for queue to drain."""
        if self._shutdown_event:
            self._shutdown_event.set()
        if self._event_queue and self._callback_threads:
            # Put sentinels to wake up all workers (with highest priority to ensure they're processed)
            try:
                import time
                sentinel_timestamp = time.time()
                # Use counter -1 to ensure sentinels are processed first among priority 0 items
                with self._queue_counter_lock:
                    sentinel_counter = self._queue_counter - 1
                # Send one sentinel per worker thread
                for _ in range(len(self._callback_threads)):
                    # Priority 0, with timestamp and counter for proper ordering
                    self._event_queue.put((0, sentinel_timestamp, sentinel_counter, None), timeout=0.1)
                    sentinel_counter -= 1  # Ensure unique counters
            except queue.Full:
                pass
        # Wait for all worker threads to finish
        for thread in self._callback_threads:
            if thread.is_alive():
                thread.join(timeout=5.0)
        self._callback_threads = []
        
    def _callback_worker(self) -> None:
        """Background worker thread that processes queued events.
        
        Processes events in priority order (NodeStart > NodeFinished > others)
        while maintaining chronological order within each priority level.
        """
        while not self._shutdown_event.is_set():
            event_data = None
            try:
                # Get event with timeout to periodically check shutdown
                # PriorityQueue returns (priority, timestamp, counter, item) tuples
                # We unpack all components but only use priority, timestamp ordering
                _, _, _, event_data = self._event_queue.get(timeout=0.1)
                if event_data is None:  # Sentinel to shutdown
                    break
                
                callback_func, event_msg = event_data
                callback_func(event_msg)
                
            except queue.Empty:
                continue
            finally:
                # Always call task_done() exactly once per successfully retrieved item
                if event_data is not None:
                    self._event_queue.task_done()

    def _get_event_priority(self, event: EventMsg) -> int:
        """Get priority for an event. Lower number = higher priority.
        
        Priority levels:
        - 0: NodeStart (highest - must create tasks before other events)
        - 1: NodeFinished (medium - update task status)
        - 2: Everything else (lowest - logging, etc.)
        
        Note: Within the same priority level, events are processed in chronological
        order using timestamps to maintain exact event sequence.
        """
        event_name = event.info.name
        if event_name == "NodeStart":
            return 0
        elif event_name == "NodeFinished":
            return 1
        else:
            return 2
    
    def _get_event_timestamp(self, event: EventMsg) -> float:
        """Get the timestamp for an event, falling back to current time if not available."""
        try:
            # Try to get timestamp from dbt event
            if hasattr(event.info, 'ts') and event.info.ts is not None:
                return float(event.info.ts)  # type: ignore[reportUnknownMemberType]
        except (AttributeError, TypeError, ValueError):
            pass
        # Fallback to current time
        import time
        return time.time()

    def _queue_callback(
        self, 
        callback_func: Callable[[EventMsg], None], 
        event: EventMsg,
        priority: Optional[int] = None
    ) -> None:
        """Helper method to queue a callback for background processing.
        
        Events are queued with priority and timestamp to maintain both:
        1. Priority ordering (NodeStart > NodeFinished > others)
        2. Chronological ordering within the same priority level
        
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
        
        # Get timestamp for chronological ordering within same priority
        timestamp = self._get_event_timestamp(event)
        
        # Get a unique counter value for tiebreaking (ensures items with same priority
        # and timestamp can be ordered without comparing EventMsg objects)
        with self._queue_counter_lock:
            counter = self._queue_counter
            self._queue_counter += 1
        
        # Queue the callback with (priority, timestamp, counter, callback_data)
        # This ensures: priority first, then chronological order, then insertion order
        try:
            self._event_queue.put(
                (priority, timestamp, counter, (callback_func, event)), 
                block=False
            )
        except queue.Full:
            # If queue is full, fall back to synchronous processing
            # This prevents blocking dbt but may slow it down
            callback_func(event)

    def _event_level_to_log_level(self, event_level: EventLevel) -> int:
        """Convert dbt EventLevel to Python logging level."""
        if event_level == EventLevel.DEBUG or event_level == EventLevel.TEST:
            return logging.DEBUG
        elif event_level == EventLevel.INFO:
            return logging.INFO
        elif event_level == EventLevel.WARN:
            return logging.WARNING
        elif event_level == EventLevel.ERROR:
            return logging.ERROR
        else:
            return logging.INFO

    def _should_log_event(self, event_level: EventLevel, configured_level: EventLevel) -> bool:
        """Check if an event should be logged based on the configured log level.
        
        Events are logged if their level is greater than or equal to the configured level.
        Ordering: DEBUG < TEST < INFO < WARN < ERROR
        
        Args:
            event_level: The level of the event to check
            configured_level: The configured log level threshold
            
        Returns:
            True if the event should be logged, False otherwise
        """
        # Convert both levels to numeric values for comparison
        event_level_num = self._event_level_to_log_level(event_level)
        configured_level_num = self._event_level_to_log_level(configured_level)
        
        # Log if event level >= configured level
        return event_level_num >= configured_level_num

    def _create_logging_callback(
        self,
        task_state: NodeTaskTracker,
        log_level: EventLevel,
        context: dict[str, Any],
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for logging dbt events.
        
        Directly emits logs to Prefect using the client API with timestamps extracted
        from dbt events. This ensures logs appear in exact chronological order with
        their original timestamps, even if processed asynchronously.
        """
        
        def logging_callback(event: EventMsg) -> None:
            """Synchronous logging callback - emits logs directly to Prefect with dbt timestamps."""
            # Skip logging for NodeStart and NodeFinished events - they have their own callbacks
            if event.info.name in ("NodeStart", "NodeFinished"):
                return
            
            # Check if event level meets the configured log level threshold
            if not self._should_log_event(event.info.level, log_level):
                return
            
            # Extract timestamp from dbt event
            event_timestamp = self._extract_event_timestamp(event)
            if event_timestamp is None:
                # Fallback to current time if no timestamp available
                event_timestamp = time.time()
            
            # Get flow_run_id and task_run_id from context
            flow_run_id: Optional[UUID] = None
            task_run_id: Optional[UUID] = None
            flow_run_name: Optional[str] = None
            task_run_name: Optional[str] = None
            node_id: Optional[str] = None
            
            event_data = MessageToDict(event.data, preserving_proto_field_name=True)
            
            # Handle logging for all events with node_info
            if event_data.get("node_info"):
                node_id = self._get_dbt_event_node_id(event)
                
                # Skip logging for skipped nodes
                if node_id in self._skipped_nodes:
                    return
                
                flow_run_context: Optional[dict[str, Any]] = context.get(
                    "flow_run_context"
                )
                if flow_run_context:
                    flow_run = flow_run_context.get("flow_run")
                    if flow_run:
                        flow_run_id_value = flow_run.get("id")
                        if flow_run_id_value:
                            flow_run_id = UUID(str(flow_run_id_value)) if isinstance(flow_run_id_value, (str, UUID)) else flow_run_id_value
                        flow_run_name = flow_run.get("name")
                    
                # Get task_run_id and task_run_name from tracker
                task_run_id_uuid = task_state.get_task_run_id(node_id)
                if task_run_id_uuid:
                    task_run_id = task_run_id_uuid
                    task_run_name = task_state.get_task_run_name(node_id)
            else:
                # Get flow_run_id for events without node_info
                try:
                    with hydrated_context(context) as run_context:
                        if hasattr(run_context, "flow_run") and run_context.flow_run:
                            flow_run_id = run_context.flow_run.id
                            flow_run_name = run_context.flow_run.name
                        elif hasattr(run_context, "task_run") and run_context.task_run:
                            flow_run_id = run_context.task_run.flow_run_id
                            task_run_id = run_context.task_run.id
                            task_run_name = run_context.task_run.name
                except MissingContextError:
                    pass

            # Only emit log if we have at least a flow_run_id
            if flow_run_id:
                # Get log message
                message = self.get_dbt_event_msg(event)
                
                # Convert dbt event level to logging level
                log_level_int = self._event_level_to_log_level(event.info.level)
                
                # Logger name for Prefect console formatting
                logger_name = "prefect.task_runs" if task_run_id else "prefect.flow_runs"
                
                # Write to terminal using Prefect's console handler
                # This ensures logs appear in the terminal with proper Prefect formatting
                try:
                    logger = get_logger(logger_name)
                    # Create a LogRecord with the dbt event timestamp
                    # Prefect formatters require specific fields based on logger name:
                    # - prefect.task_runs requires task_run_name
                    # - prefect.flow_runs requires flow_run_name
                    # Set send_to_api=False to prevent APILogHandler from processing,
                    # since we'll send to API directly with the correct timestamp
                    extra_dict: dict[str, Any] = {
                        "flow_run_id": str(flow_run_id),
                        "flow_run_name": flow_run_name or "<unknown>",
                        "send_to_api": False,  # Prevent APILogHandler from sending (we'll send directly)
                    }
                    if task_run_id:
                        extra_dict["task_run_id"] = str(task_run_id)
                        # task_run_name is required for prefect.task_runs logger
                        extra_dict["task_run_name"] = task_run_name or "<unknown>"
                    
                    record = logger.makeRecord(
                        logger_name,
                        log_level_int,
                        "",  # filename (not used)
                        0,   # lineno (not used)
                        message,
                        (),  # args
                        None,  # exc_info
                        func="",  # funcName
                        extra=extra_dict,
                        sinfo=None,  # stack_info
                    )
                    # Override the timestamp with the dbt event timestamp
                    record.created = event_timestamp
                    record.msecs = (event_timestamp % 1) * 1000
                    # Emit through the logger (which will use PrefectConsoleHandler for terminal output)
                    # The send_to_api=False flag prevents APILogHandler from sending to API
                    logger.handle(record)
                except Exception:
                    # Silently fail if console logging fails to avoid blocking dbt
                    pass
                
                # Create log entry with dbt event timestamp for API
                log_entry = LogCreate(
                    name=logger_name,
                    level=log_level_int,
                    message=message,
                    timestamp=from_timestamp(event_timestamp),
                    flow_run_id=flow_run_id,
                    task_run_id=task_run_id,
                )
                
                # Emit log directly to Prefect API
                try:
                    self.client.create_logs([log_entry])
                except Exception:
                    # Silently fail if log creation fails to avoid blocking dbt
                    # This can happen if the client is disconnected or the run doesn't exist
                    pass

        return logging_callback

    def _create_node_started_callback(
        self, task_state: NodeTaskTracker, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for starting tasks when nodes start."""
        
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
                    self._call_task(
                        task_state, manifest_node, context, enable_assets
                    )

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
        add_test_edges: bool = False,
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for ending tasks when nodes finish."""
        
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
                    event_data = MessageToDict(event.data, preserving_proto_field_name=True)
                    # Store the status before ending the task
                    event_message = self.get_dbt_event_msg(event)
                    task_state.set_node_status(node_id, event_data, event_message)

                    node_info: Optional[dict[str, Any]] = event_data.get(
                        "node_info"
                    )
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

        callbacks = (
            [
                self._create_logging_callback(task_state, self.log_level, context),
                self._create_node_started_callback(task_state, context),
                self._create_node_finished_callback(
                    task_state, add_test_edges=add_test_edges
                ),
            ]
            if in_flow_or_task_run or self._force_nodes_as_tasks
            else []
        )

        # Determine which command is being invoked
        command_name = None
        for arg in args_copy:
            if not arg.startswith("-"):
                command_name = arg
                break

        # Build invoke_kwargs with only parameters valid for this command
        invoke_kwargs = {}

        # Get valid parameters for the command if we can determine it
        valid_params = None
        if command_name:
            from dbt.cli.main import cli

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
