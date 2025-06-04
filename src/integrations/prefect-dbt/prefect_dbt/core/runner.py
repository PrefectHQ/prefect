"""
Runner for dbt commands
"""

import json
import os
from typing import Any, Callable, Optional

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
from prefect.events import emit_event
from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas.events import RelatedResource
from prefect.exceptions import MissingContextError
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.engine import asset_as_related, asset_as_resource
from prefect_dbt.core.profiles import aresolve_profiles_yml, resolve_profiles_yml
from prefect_dbt.core.settings import PrefectDbtSettings
from prefect_dbt.utilities import format_resource_id

FAILURE_STATUSES = [
    RunStatus.Error,
    TestStatus.Error,
    TestStatus.Fail,
    FreshnessStatus.Error,
    FreshnessStatus.RuntimeErr,
]
FAILURE_MSG = '{resource_type} {resource_name} {status}ed with message: "{message}"'


NODE_TYPES_TO_EMIT_MATERIALIZATION_EVENTS = [
    NodeType.Model,
    NodeType.Seed,
    NodeType.Snapshot,
]
NODE_TYPES_TO_EMIT_OBSERVATION_EVENTS = [
    NodeType.Exposure,
    NodeType.Source,
]


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
        self.manifest: Optional[Manifest] = manifest
        self.client = client or get_client()
        self.raise_on_failure = raise_on_failure

    def _set_manifest_from_project_dir(self):
        """Set the manifest from the project directory"""
        try:
            with open(
                os.path.join(self.settings.project_dir, "target", "manifest.json"), "r"
            ) as f:
                self.manifest = Manifest.from_dict(json.load(f))  # type: ignore[reportUnknownMemberType]
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
        adapter_type: str,
        manifest_node: ManifestNode,
        related_prefect_context: list[RelatedResource],
    ) -> list[RelatedResource]:
        """Get upstream nodes for a given node"""
        upstream_manifest_nodes: list[RelatedResource] = []

        for depends_on_node in manifest_node.depends_on_nodes:  # type: ignore[reportUnknownMemberType]
            depends_manifest_node = self.manifest.nodes.get(depends_on_node)  # type: ignore[reportUnknownMemberType]

            if not depends_manifest_node or not self._get_node_prefect_config(
                depends_manifest_node
            ).get("emit_asset_events", True):
                continue

            if not depends_manifest_node.relation_name:
                raise ValueError("Relation name not found in manifest")

            asset = Asset(
                key=format_resource_id(
                    adapter_type, depends_manifest_node.relation_name
                ),
                properties=AssetProperties(
                    name=depends_manifest_node.name,
                    description=depends_manifest_node.description,
                    owners=[owner]
                    if (owner := depends_manifest_node.config.meta.get("owner"))
                    and isinstance(owner, str)
                    else None,
                ),
            )

            upstream_manifest_nodes.append(RelatedResource(asset_as_related(asset)))

            if (
                depends_manifest_node.resource_type
                in NODE_TYPES_TO_EMIT_OBSERVATION_EVENTS
            ):
                emit_event(
                    event="prefect.asset.observation.succeeded",
                    resource=asset_as_resource(asset),
                    related=related_prefect_context,
                )

        return upstream_manifest_nodes

    def _emit_asset_events(
        self,
        manifest_node: ManifestNode,
        related_prefect_context: list[RelatedResource],
        dbt_event: EventMsg | None = None,
    ):
        """Emit asset events for a given node"""
        assert self.manifest is not None  # for type checking

        if manifest_node.resource_type not in NODE_TYPES_TO_EMIT_MATERIALIZATION_EVENTS:
            return

        adapter_type = self.manifest.metadata.adapter_type
        if not adapter_type:
            raise ValueError("Adapter type not found in manifest")

        if not manifest_node.relation_name:
            raise ValueError("Relation name not found in manifest")

        resource: dict[str, str] = asset_as_resource(
            Asset(
                key=format_resource_id(adapter_type, manifest_node.relation_name),
                properties=AssetProperties(
                    name=manifest_node.name,
                    description=manifest_node.description,
                    owners=[owner]
                    if (owner := manifest_node.config.meta.get("owner"))
                    and isinstance(owner, str)
                    else None,
                ),
            )
        )

        related: list[RelatedResource] = []
        related.extend(related_prefect_context)
        related.extend(
            self._get_upstream_manifest_nodes(
                adapter_type, manifest_node, related_prefect_context
            )
        )
        related.append(
            RelatedResource(
                root={
                    "prefect.resource.id": "dbt",
                    "prefect.resource.role": "asset-materialized-by",
                }
            )
        )

        if dbt_event:
            event_data = MessageToDict(dbt_event.data, preserving_proto_field_name=True)
            node_info = event_data.get("node_info")
            node_status = node_info.get("node_status") if node_info else None
            status = (
                "succeeded"
                if node_status
                in [
                    NodeStatus.Success,
                    NodeStatus.Skipped,
                    NodeStatus.Pass,
                    NodeStatus.PartialSuccess,
                    NodeStatus.Warn,
                ]
                else "failed"
            )
        else:
            status = "succeeded"

        payload: dict[str, Any] = {}
        if dbt_event:
            payload = MessageToDict(dbt_event.data, preserving_proto_field_name=True)

        if manifest_node.resource_type == NodeType.Model and manifest_node.compiled:
            payload["query"] = manifest_node.compiled_code

        emit_event(
            event=f"prefect.asset.materialization.{status}",
            resource=resource,
            related=related,
            payload=payload,
        )

    def _get_dbt_event_msg(self, event: EventMsg) -> str:
        return event.info.msg  # type: ignore[reportUnknownMemberType]

    def _create_logging_callback(
        self, log_level: EventLevel
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for logging dbt events.

        Returns:
            A callback function that logs dbt events using the Prefect logger.
            Debug-level events are filtered out.
        """
        try:
            logger = get_run_logger()
        except MissingContextError:
            logger = None

        def logging_callback(event: EventMsg):
            if logger is not None:
                logger.setLevel(log_level.value.upper())
                if (
                    event.info.level == EventLevel.DEBUG
                    or event.info.level == EventLevel.TEST
                ):
                    logger.debug(self._get_dbt_event_msg(event))
                elif event.info.level == EventLevel.INFO:
                    logger.info(self._get_dbt_event_msg(event))
                elif event.info.level == EventLevel.WARN:
                    logger.warning(self._get_dbt_event_msg(event))
                elif event.info.level == EventLevel.ERROR:
                    logger.error(self._get_dbt_event_msg(event))

        return logging_callback

    def _get_dbt_event_node_id(self, event: EventMsg) -> str:
        return event.data.node_info.unique_id  # type: ignore[reportUnknownMemberType]

    def _create_events_callback(
        self, related_prefect_context: list[RelatedResource]
    ) -> Callable[[EventMsg], None]:
        """Creates a callback function for emitting asset events.

        Args:
            related_prefect_context: List of related Prefect resources to include
                in asset tracking.

        Returns:
            A callback function that emits asset events when dbt nodes finish executing.
        """

        def events_callback(event: EventMsg):
            if event.info.name == "NodeFinished":
                if self.manifest is None:
                    self._set_manifest_from_project_dir()

                assert self.manifest is not None  # for type checking
                node_id = self._get_dbt_event_node_id(event)

                assert isinstance(node_id, str)

                manifest_node = self.manifest.nodes.get(node_id)

                if manifest_node:
                    prefect_config = manifest_node.config.meta.get("prefect", {})
                    enable_asset_events = prefect_config.get(
                        "enable_asset_events", True
                    )

                    try:
                        if enable_asset_events:
                            self._emit_asset_events(
                                manifest_node, related_prefect_context, event
                            )
                    except Exception as e:
                        print(e)

        return events_callback

    async def ainvoke(self, args: list[str], **kwargs: Any) -> dbtRunnerResult:
        """Asynchronously invokes a dbt command.

        Args:
            args: List of dbt command arguments
            **kwargs: Additional keyword arguments to pass to dbt

        Returns:
            The result of the dbt command execution
        """
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
                self._create_logging_callback(self.settings.log_level),
                self._create_events_callback(related_prefect_context),
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
        """Synchronously invokes a dbt command.

        Args:
            args: List of dbt command arguments
            **kwargs: Additional keyword arguments to pass to dbt

        Returns:
            The result of the dbt command execution
        """
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
                self._create_logging_callback(self.settings.log_level),
                self._create_events_callback(related_prefect_context),
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

    async def aemit_materialization_events(self):
        """Asynchronously emit asset events for all relevant nodes in the dbt manifest.

        This method parses the manifest if not already loaded and emits asset events for
        models, seeds, and exposures.
        """
        if self.manifest is None:
            self._set_manifest_from_project_dir()

        assert self.manifest is not None  # for type checking

        related_prefect_context = await related_resources_from_run_context(self.client)

        for manifest_node in self.manifest.nodes.values():
            self._emit_asset_events(manifest_node, related_prefect_context)

    def emit_materialization_events(self):
        """Synchronously emit asset events for all relevant nodes in the dbt manifest.

        This method parses the manifest if not already loaded and emits asset events for
        models, seeds, and exposures.
        """
        if self.manifest is None:
            self._set_manifest_from_project_dir()

        assert self.manifest is not None  # for type checking

        related_prefect_context = run_coro_as_sync(
            related_resources_from_run_context(self.client),
        )
        assert related_prefect_context is not None

        for manifest_node in self.manifest.nodes.values():
            self._emit_asset_events(manifest_node, related_prefect_context)
