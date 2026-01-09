"""
Data models for SDK generation.

This module contains the internal data models used to represent workspace data
fetched from the Prefect API, which are then passed to the template renderer.

Note: These models are internal to SDK generation and not part of the public API.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkPoolInfo:
    """Information about a work pool needed for SDK generation.

    Attributes:
        name: The work pool name as it appears in Prefect.
        pool_type: The work pool type (e.g., "kubernetes", "docker", "process").
        job_variables_schema: JSON Schema dict for the work pool's job variables.
            This is the full schema object (e.g., {"type": "object", "properties": {...}})
            from base_job_template["variables"]. Can be empty dict if no job
            variables are defined.
    """

    name: str
    pool_type: str
    job_variables_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentInfo:
    """Information about a deployment needed for SDK generation.

    Attributes:
        name: The deployment name (just the deployment part, not flow/deployment).
        flow_name: The name of the flow this deployment belongs to.
        full_name: The full deployment name in "flow-name/deployment-name" format.
        parameter_schema: JSON Schema dict for the flow's parameters.
            This comes from the deployment's parameter_openapi_schema field.
            Can be empty dict or None if the flow has no parameters.
        work_pool_name: Name of the work pool this deployment uses.
            Can be None if the deployment doesn't use a work pool.
        description: Optional deployment description for docstrings.
    """

    name: str
    flow_name: str
    full_name: str
    parameter_schema: dict[str, Any] | None = None
    work_pool_name: str | None = None
    description: str | None = None


@dataclass
class FlowInfo:
    """Information about a flow and its deployments.

    Groups deployments by their parent flow for organized SDK generation.

    Attributes:
        name: The flow name.
        deployments: List of deployments belonging to this flow.
    """

    name: str
    deployments: list[DeploymentInfo] = field(default_factory=list)


@dataclass
class SDKGenerationMetadata:
    """Metadata about the SDK generation process.

    Attributes:
        generation_time: ISO 8601 timestamp of when the SDK was generated.
        prefect_version: Version of Prefect used for generation.
        workspace_name: Name of the workspace (if applicable).
        api_url: The Prefect API URL used.
    """

    generation_time: str
    prefect_version: str
    workspace_name: str | None = None
    api_url: str | None = None


@dataclass
class SDKData:
    """Complete data needed for SDK generation.

    This is the top-level container passed to the template renderer.

    Attributes:
        metadata: Generation metadata (time, version, workspace).
        flows: Dictionary mapping flow names to FlowInfo objects.
        work_pools: Dictionary mapping work pool names to WorkPoolInfo objects.
    """

    metadata: SDKGenerationMetadata
    flows: dict[str, FlowInfo] = field(default_factory=dict)
    work_pools: dict[str, WorkPoolInfo] = field(default_factory=dict)

    @property
    def deployment_count(self) -> int:
        """Total number of deployments across all flows."""
        return sum(len(flow.deployments) for flow in self.flows.values())

    @property
    def flow_count(self) -> int:
        """Number of flows."""
        return len(self.flows)

    @property
    def work_pool_count(self) -> int:
        """Number of work pools."""
        return len(self.work_pools)

    @property
    def deployment_names(self) -> list[str]:
        """List of all deployment full names (derived from flows).

        Returns names sorted alphabetically for deterministic code generation.
        """
        names: list[str] = []
        for flow in self.flows.values():
            for deployment in flow.deployments:
                names.append(deployment.full_name)
        return sorted(names)

    def all_deployments(self) -> list[DeploymentInfo]:
        """Return a flat list of all deployments.

        Returns deployments sorted by full_name for deterministic code generation.
        """
        deployments: list[DeploymentInfo] = []
        for flow in self.flows.values():
            deployments.extend(flow.deployments)
        return sorted(deployments, key=lambda d: d.full_name)
