"""
Runner for dbt commands
"""

import json
import os
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
from dbt.cli.main import dbtRunner
from dbt.compilation import Linker
from dbt.config.runtime import RuntimeConfig
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt.contracts.state import (
    load_result_state,  # type: ignore[reportUnknownMemberType]
)
from dbt.graph.graph import Graph, UniqueId
from dbt_common.events.base_types import EventLevel, EventMsg
from google.protobuf.json_format import MessageToDict

from prefect import get_client, get_run_logger
from prefect._internal.uuid7 import uuid7
from prefect.assets import Asset, AssetProperties
from prefect.cache_policies import NO_CACHE
from prefect.client.orchestration import PrefectClient
from prefect.context import AssetContext, hydrated_context, serialize_context
from prefect.exceptions import MissingContextError
from prefect.tasks import MaterializingTask, Task, TaskOptions
from prefect_dbt.core._tracker import NodeTaskTracker
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
    ):
        self._manifest: Optional[Manifest] = manifest
        self.settings = settings or PrefectDbtSettings()
        self.raise_on_failure = raise_on_failure
        self.client = client or get_client()
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
        self, manifest_node: ManifestNode
    ) -> dict[str, dict[str, Any]]:
        return manifest_node.config.meta.get("prefect", {})

    def _get_upstream_manifest_nodes_and_configs(
        self,
        manifest_node: ManifestNode,
    ) -> list[tuple[ManifestNode, dict[str, Any]]]:
        """Get upstream nodes for a given node"""
        upstream_manifest_nodes: list[tuple[ManifestNode, dict[str, Any]]] = []

        for depends_on_node in manifest_node.depends_on_nodes:  # type: ignore[reportUnknownMemberType]
            depends_manifest_node = self.manifest.nodes.get(depends_on_node)  # type: ignore[reportUnknownMemberType]

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

    def _get_compiled_code(self, manifest_node: ManifestNode) -> str:
        """Get compiled code for a manifest node if it exists and is enabled."""
        if not self.include_compiled_code:
            return ""

        compiled_code_path = self._get_compiled_code_path(manifest_node)
        if os.path.exists(compiled_code_path):
            with open(compiled_code_path, "r") as f:
                code_content = f.read()
                return f"\n ### Compiled code\n```sql\n{code_content.strip()}\n```"
        return ""

    def _create_asset_from_node(
        self, manifest_node: ManifestNode, adapter_type: str
    ) -> Asset:
        """Create an Asset from a manifest node."""
        if not manifest_node.relation_name:
            raise ValueError("Relation name not found in manifest")

        asset_id = format_resource_id(adapter_type, manifest_node.relation_name)
        compiled_code = self._get_compiled_code(manifest_node)

        return Asset(
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

    def _create_logging_callback(
        self,
        task_state: NodeTaskTracker,
        log_level: EventLevel,
        context: dict[str, Any],
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for logging dbt events."""

        def logging_callback(event: EventMsg):
            event_data = MessageToDict(event.data, preserving_proto_field_name=True)
            if (
                event_data.get("node_info")
                and (node_id := self._get_dbt_event_node_id(event))
                not in self._skipped_nodes
            ):
                flow_run_context: Optional[dict[str, Any]] = context.get(
                    "flow_run_context"
                )
                logger = task_state.get_task_logger(
                    node_id,
                    flow_run_context.get("flow_run") if flow_run_context else None,
                    flow_run_context.get("flow") if flow_run_context else None,
                )
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
        self, task_state: NodeTaskTracker, context: dict[str, Any]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for starting tasks when nodes start."""

        def node_started_callback(event: EventMsg):
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
                    try:
                        self._call_task(
                            task_state, manifest_node, context, enable_assets
                        )
                    except Exception as e:
                        print(e)

        return node_started_callback

    def _create_node_finished_callback(
        self,
        task_state: NodeTaskTracker,
        add_test_edges: bool = False,
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for ending tasks when nodes finish."""

        def node_finished_callback(event: EventMsg):
            if event.info.name == "NodeFinished":
                node_id = self._get_dbt_event_node_id(event)
                if node_id in self._skipped_nodes:
                    return

                manifest_node, _ = self._get_manifest_node_and_config(node_id)

                if manifest_node:
                    try:
                        # Store the status before ending the task
                        event_data = MessageToDict(
                            event.data, preserving_proto_field_name=True
                        )
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
                    except Exception as e:
                        print(e)

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

        # Add settings to kwargs if they're set
        invoke_kwargs = {
            "profiles_dir": str(self.profiles_dir),
            "project_dir": str(self.project_dir),
            "target_path": str(self.target_path),
            "log_level": "none" if in_flow_or_task_run else str(self.log_level.value),
            "log_level_file": str(self.log_level.value),
            **kwargs,
        }

        with self.settings.resolve_profiles_yml() as profiles_dir:
            invoke_kwargs["profiles_dir"] = profiles_dir

            res = dbtRunner(callbacks=callbacks).invoke(  # type: ignore[reportUnknownMemberType]
                args_copy,
                **invoke_kwargs,
            )

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
