"""
Runner for dbt commands
"""

import os
from typing import Any, Callable, Optional

from dbt.artifacts.resources.types import NodeType
from dbt.artifacts.schemas.results import FreshnessStatus, RunStatus, TestStatus
from dbt.artifacts.schemas.run import RunExecutionResult
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt_common.events.base_types import EventLevel, EventMsg
from google.protobuf.json_format import MessageToDict

from prefect import get_client, get_run_logger
from prefect._experimental.lineage import emit_external_resource_lineage
from prefect.client.orchestration import PrefectClient
from prefect.events import emit_event
from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas.events import RelatedResource
from prefect.exceptions import MissingContextError
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_dbt.core.profiles import aresolve_profiles_yml, resolve_profiles_yml
from prefect_dbt.core.settings import PrefectDbtSettings

FAILURE_STATUSES = [
    RunStatus.Error,
    TestStatus.Error,
    TestStatus.Fail,
    FreshnessStatus.Error,
    FreshnessStatus.RuntimeErr,
]
FAILURE_MSG = '{resource_type} {resource_name} {status}ed with message: "{message}"'

REQUIRES_MANIFEST = [
    "build",
    "compile",
    "docs",
    "list",
    "ls",
    "run",
    "run-operation",
    "seed",
    "show",
    "snapshot",
    "source",
    "test",
]
NODE_TYPES_TO_EMIT_LINEAGE = [
    NodeType.Model,
    NodeType.Seed,
    NodeType.Snapshot,
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

    def _get_manifest_depends_on_nodes(self, manifest_node: ManifestNode) -> list[str]:
        """Type completeness wrapper for manifest_node.depends_on_nodes"""
        return manifest_node.depends_on_nodes  # type: ignore[reportUnknownMemberType]

    def _emit_lineage_event(
        self,
        manifest_node: ManifestNode,
        related_prefect_context: list[RelatedResource],
    ):
        """Emit a lineage event for a given node"""
        assert self.manifest is not None  # for type checking

        if manifest_node.resource_type not in NODE_TYPES_TO_EMIT_LINEAGE:
            return

        adapter_type = self.manifest.metadata.adapter_type
        node_name = manifest_node.name
        primary_relation_name = (
            manifest_node.relation_name.replace('"', "").replace(".", "/")
            if manifest_node.relation_name
            else None
        )
        related_resources: list[dict[str, str]] = []

        # Add related resources from the prefect context
        for realted_resource in related_prefect_context:
            related_resources.append(realted_resource.model_dump())

        # Add upstream nodes from the manifest
        upstream_manifest_nodes: list[dict[str, Any]] = []
        for depends_on_node in self._get_manifest_depends_on_nodes(manifest_node):
            depends_manifest_node = self.manifest.nodes.get(depends_on_node)
            if depends_manifest_node is not None:
                depends_node_prefect_config: dict[str, dict[str, Any]] = (
                    depends_manifest_node.config.meta.get("prefect", {})
                )
                depends_relation_name = (
                    depends_manifest_node.relation_name.replace('"', "").replace(
                        ".", "/"
                    )
                    if depends_manifest_node.relation_name
                    else None
                )
                if depends_node_prefect_config.get("emit_lineage_events", True):
                    upstream_manifest_nodes.append(
                        {
                            "prefect.resource.id": f"{adapter_type}://{depends_relation_name}",
                            "prefect.resource.lineage-group": depends_node_prefect_config.get(
                                "lineage_group", "global"
                            ),
                            "prefect.resource.role": depends_manifest_node.resource_type,
                            "prefect.resource.name": depends_manifest_node.name,
                        }
                    )

        node_prefect_config: dict[str, Any] = manifest_node.config.meta.get(
            "prefect", {}
        )

        # Add related resources from the node config
        upstream_config_resources: list[dict[str, str]] = []
        upstream_resources = node_prefect_config.get("upstream_resources")
        if upstream_resources:
            for upstream_resource in upstream_resources:
                if (resource_id := upstream_resource.get("id")) is None:
                    raise ValueError("Upstream resources must have an id")
                elif (resource_name := upstream_resource.get("name")) is None:
                    raise ValueError("Upstream resources must have a name")
                else:
                    resource: dict[str, str] = {
                        "prefect.resource.id": resource_id,
                        "prefect.resource.lineage-group": upstream_resource.get(
                            "lineage_group", "global"
                        ),
                        "prefect.resource.role": upstream_resource.get("role", "table"),
                        "prefect.resource.name": resource_name,
                    }
                upstream_config_resources.append(resource)

        primary_resource: dict[str, Any] = {
            "prefect.resource.id": f"{adapter_type}://{primary_relation_name}",
            "prefect.resource.lineage-group": node_prefect_config.get(
                "lineage_group", "global"
            ),
            "prefect.resource.role": manifest_node.resource_type,
            "prefect.resource.name": node_name,
        }

        if related_prefect_context:
            run_coro_as_sync(
                emit_external_resource_lineage(
                    context_resources=related_prefect_context,
                    upstream_resources=upstream_manifest_nodes
                    + upstream_config_resources,
                    downstream_resources=[primary_resource],
                )
            )

    def _emit_node_event(
        self,
        manifest_node: ManifestNode,
        related_prefect_context: list[RelatedResource],
        dbt_event: EventMsg,
    ):
        """Emit a generic event for a given node"""
        assert self.manifest is not None  # for type checking

        related_resources: list[dict[str, str]] = []

        # Add related resources from the prefect context
        for resource in related_prefect_context:
            related_resources.append(resource.model_dump())

        event_data = MessageToDict(dbt_event.data, preserving_proto_field_name=True)
        node_info = event_data.get("node_info")
        node_status = node_info.get("node_status") if node_info else None

        emit_event(
            event=f"{manifest_node.name} {node_status}",
            resource={
                "prefect.resource.id": f"dbt.{manifest_node.unique_id}",
                "prefect.resource.name": manifest_node.name,
                "dbt.node.status": node_status or "",
            },
            related=related_resources,
            payload=event_data,
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
        """Creates a callback function for tracking dbt node lineage.

        Args:
            related_prefect_context: List of related Prefect resources to include
                in lineage tracking.

        Returns:
            A callback function that emits lineage events when dbt nodes finish executing.
        """

        def events_callback(event: EventMsg):
            if event.info.name == "NodeFinished" and self.manifest is not None:
                node_id = self._get_dbt_event_node_id(event)
                assert isinstance(node_id, str)

                manifest_node = self.manifest.nodes.get(node_id)

                if manifest_node:
                    prefect_config = manifest_node.config.meta.get("prefect", {})
                    emit_events = prefect_config.get("emit_events", True)
                    emit_node_events = prefect_config.get("emit_node_events", True)
                    emit_lineage_events = prefect_config.get(
                        "emit_lineage_events", True
                    )

                    try:
                        if emit_events and emit_node_events:
                            self._emit_node_event(
                                manifest_node, related_prefect_context, event
                            )
                        if emit_events and emit_lineage_events:
                            self._emit_lineage_event(
                                manifest_node, related_prefect_context
                            )
                    except Exception as e:
                        print(e)

        return events_callback

    def parse(self, **kwargs: Any):
        """Parses the dbt project and loads the manifest.

        This method runs the dbt parse command to generate and load the manifest
        if it hasn't been loaded already.

        Raises:
            ValueError: If the manifest fails to load.
        """
        if self.manifest is None:
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
                res: dbtRunnerResult = dbtRunner(
                    callbacks=[self._create_logging_callback(self.settings.log_level)]
                ).invoke(  # type: ignore[reportUnknownMemberType]
                    ["parse"], **invoke_kwargs
                )

            if not res.success:
                raise ValueError(f"Failed to load manifest: {res.exception}")

            assert isinstance(res.result, Manifest), (
                "Expected manifest result from dbt parse"
            )

            self.manifest = res.result

    async def ainvoke(self, args: list[str], **kwargs: Any):
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

            needs_manifest = any(arg in REQUIRES_MANIFEST for arg in args)
            if self.manifest is None and "parse" not in args and needs_manifest:
                self.parse()

            callbacks = [
                self._create_logging_callback(self.settings.log_level),
                self._create_events_callback(related_prefect_context),
            ]
            res = dbtRunner(callbacks=callbacks).invoke(args, **invoke_kwargs)

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

            needs_manifest = any(arg in REQUIRES_MANIFEST for arg in args)
            if self.manifest is None and "parse" not in args and needs_manifest:
                self.parse()

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

    async def aemit_lineage_events(self):
        """Asynchronously emit lineage events for all relevant nodes in the dbt manifest.

        This method parses the manifest if not already loaded and emits lineage events for
        models, seeds, and exposures.
        """
        if self.manifest is None:
            self.parse()

        assert self.manifest is not None  # for type checking

        related_prefect_context = await related_resources_from_run_context(self.client)

        for manifest_node in self.manifest.nodes.values():
            self._emit_lineage_event(manifest_node, related_prefect_context)

    def emit_lineage_events(self):
        """Synchronously emit lineage events for all relevant nodes in the dbt manifest.

        This method parses the manifest if not already loaded and emits lineage events for
        models, seeds, and exposures.
        """
        if self.manifest is None:
            self.parse()

        assert self.manifest is not None  # for type checking

        related_prefect_context = run_coro_as_sync(
            related_resources_from_run_context(self.client),
        )
        assert related_prefect_context is not None

        for manifest_node in self.manifest.nodes.values():
            self._emit_lineage_event(manifest_node, related_prefect_context)
