"""
SDK data fetcher module.

This module is responsible for fetching deployment and work pool data from the
Prefect API and converting it to the internal data models used by the SDK generator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

import prefect
from prefect._sdk.models import (
    DeploymentInfo,
    FlowInfo,
    SDKData,
    SDKGenerationMetadata,
    WorkPoolInfo,
)
from prefect.client.schemas.filters import (
    DeploymentFilter,
    DeploymentFilterName,
    FlowFilter,
    FlowFilterId,
    FlowFilterName,
)
from prefect.exceptions import ObjectNotFound
from prefect.settings.context import get_current_settings

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.responses import DeploymentResponse


@dataclass
class FetchResult:
    """Result of fetching SDK data from the API.

    Attributes:
        data: The SDK data if fetching was successful.
        warnings: List of warnings encountered during fetching.
        errors: List of errors encountered during fetching (non-fatal).
    """

    data: SDKData
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SDKFetcherError(Exception):
    """Base exception for SDK fetcher errors."""

    pass


class AuthenticationError(SDKFetcherError):
    """Raised when authentication with the Prefect API fails."""

    pass


class APIConnectionError(SDKFetcherError):
    """Raised when the Prefect API cannot be reached."""

    pass


class NoDeploymentsError(SDKFetcherError):
    """Raised when no deployments are found."""

    pass


async def _check_authentication(client: "PrefectClient") -> None:
    """Check if the client is authenticated.

    Args:
        client: The Prefect client to check.

    Raises:
        AuthenticationError: If not authenticated.
        APIConnectionError: If the API cannot be reached.
    """
    try:
        exc = await client.api_healthcheck()
        if exc is not None:
            # Check if it's an authentication error
            exc_str = str(exc).lower()
            if (
                "unauthorized" in exc_str
                or "forbidden" in exc_str
                or "401" in exc_str
                or "403" in exc_str
            ):
                raise AuthenticationError(
                    "Not authenticated. Run `prefect cloud login` or configure "
                    "PREFECT_API_URL."
                )
            raise APIConnectionError(
                f"Could not connect to Prefect API at {client.api_url}. "
                f"Check your configuration. Error: {exc}"
            )
    except Exception as e:
        if isinstance(e, (AuthenticationError, APIConnectionError)):
            raise
        raise APIConnectionError(
            f"Could not connect to Prefect API at {client.api_url}. "
            f"Check your configuration. Error: {e}"
        ) from e


async def _fetch_deployments(
    client: "PrefectClient",
    flow_filter: FlowFilter | None = None,
    deployment_filter: DeploymentFilter | None = None,
) -> list["DeploymentResponse"]:
    """Fetch all deployments with pagination.

    Args:
        client: The Prefect client to use.
        flow_filter: Optional filter for flows.
        deployment_filter: Optional filter for deployments.

    Returns:
        List of deployment responses.
    """
    page_size = 200
    offset = 0
    all_deployments: list[DeploymentResponse] = []

    while True:
        deployments = await client.read_deployments(
            flow_filter=flow_filter,
            deployment_filter=deployment_filter,
            limit=page_size,
            offset=offset,
        )

        if not deployments:
            break

        all_deployments.extend(deployments)

        if len(deployments) < page_size:
            break

        offset += page_size

    return all_deployments


async def _fetch_work_pool(
    client: "PrefectClient",
    work_pool_name: str,
) -> WorkPoolInfo | None:
    """Fetch a single work pool by name.

    Args:
        client: The Prefect client to use.
        work_pool_name: The name of the work pool to fetch.

    Returns:
        WorkPoolInfo if found, None if not found.

    Raises:
        Exception: For non-ObjectNotFound errors (to be caught by gather).
    """
    try:
        work_pool = await client.read_work_pool(work_pool_name)
        # Extract job variables schema from base_job_template
        job_vars_schema: dict[str, Any] = {}
        base_job_template = work_pool.base_job_template
        if base_job_template and "variables" in base_job_template:
            variables = base_job_template["variables"]
            if isinstance(variables, dict):
                job_vars_schema = variables

        return WorkPoolInfo(
            name=work_pool.name,
            pool_type=work_pool.type,
            job_variables_schema=job_vars_schema,
        )
    except ObjectNotFound:
        return None
    # Let other exceptions propagate to be captured by gather(return_exceptions=True)


async def _fetch_work_pools_parallel(
    client: "PrefectClient",
    work_pool_names: set[str],
) -> tuple[dict[str, WorkPoolInfo], list[str]]:
    """Fetch multiple work pools in parallel.

    Args:
        client: The Prefect client to use.
        work_pool_names: Set of work pool names to fetch.

    Returns:
        Tuple of (work_pools dict, warnings list).
    """
    if not work_pool_names:
        return {}, []

    warnings: list[str] = []

    # Convert to sorted list for deterministic iteration order
    pool_names_list = sorted(work_pool_names)

    # Fetch work pools in parallel
    tasks = [_fetch_work_pool(client, name) for name in pool_names_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    work_pools: dict[str, WorkPoolInfo] = {}
    for name, result in zip(pool_names_list, results, strict=True):
        if isinstance(result, BaseException):
            warnings.append(
                f"Could not fetch work pool '{name}' - `with_infra()` will not be "
                f"generated for affected deployments: {result}"
            )
        elif result is None:
            warnings.append(
                f"Work pool '{name}' not found - `with_infra()` will not be "
                f"generated for affected deployments"
            )
        else:
            # At this point, result is WorkPoolInfo
            work_pools[name] = result

    return work_pools, warnings


async def _fetch_flows_for_deployments(
    client: "PrefectClient",
    deployment_flow_ids: set[str],
) -> tuple[dict[str, str], list[str]]:
    """Fetch flow names for the given flow IDs.

    Args:
        client: The Prefect client to use.
        deployment_flow_ids: Set of flow IDs (as strings) to look up.

    Returns:
        Tuple of (dict mapping flow_id to flow_name, list of warnings).
    """
    if not deployment_flow_ids:
        return {}, []

    warnings: list[str] = []
    flow_uuids: list[UUID] = []

    # Convert string IDs to UUIDs with defensive handling
    for fid in deployment_flow_ids:
        try:
            flow_uuids.append(UUID(fid))
        except (ValueError, TypeError) as e:
            warnings.append(f"Invalid flow ID '{fid}' - skipping: {e}")

    if not flow_uuids:
        return {}, warnings

    # Fetch flows by ID with pagination
    page_size = 200
    offset = 0
    flow_id_to_name: dict[str, str] = {}
    flow_filter = FlowFilter(id=FlowFilterId(any_=flow_uuids))

    while True:
        flows = await client.read_flows(
            flow_filter=flow_filter,
            limit=page_size,
            offset=offset,
        )

        if not flows:
            break

        for flow in flows:
            flow_id_to_name[str(flow.id)] = flow.name

        if len(flows) < page_size:
            break

        offset += page_size

    return flow_id_to_name, warnings


async def fetch_sdk_data(
    client: "PrefectClient",
    flow_names: list[str] | None = None,
    deployment_names: list[str] | None = None,
) -> FetchResult:
    """Fetch all data needed for SDK generation.

    Args:
        client: An active Prefect client.
        flow_names: Optional list of flow names to filter to.
        deployment_names: Optional list of deployment names to filter to.
            These should be in "flow-name/deployment-name" format for exact
            matching. Short names (without "/") will match any deployment
            with that name across all flows.

    Returns:
        FetchResult containing SDK data and any warnings/errors.

    Raises:
        AuthenticationError: If not authenticated.
        APIConnectionError: If the API cannot be reached.
        NoDeploymentsError: If no deployments match the filters.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Check authentication first
    await _check_authentication(client)

    # Build filters
    flow_filter: FlowFilter | None = None
    deployment_filter: DeploymentFilter | None = None

    if flow_names:
        flow_filter = FlowFilter(name=FlowFilterName(any_=flow_names))

    if deployment_names:
        # Extract just the deployment name parts (after the /)
        deploy_name_parts = []
        for full_name in deployment_names:
            if "/" in full_name:
                _, deploy_name = full_name.split("/", 1)
                deploy_name_parts.append(deploy_name)
            else:
                deploy_name_parts.append(full_name)
        deployment_filter = DeploymentFilter(
            name=DeploymentFilterName(any_=deploy_name_parts)
        )

    # Fetch deployments
    deployment_responses = await _fetch_deployments(
        client,
        flow_filter=flow_filter,
        deployment_filter=deployment_filter,
    )

    if not deployment_responses:
        if flow_names or deployment_names:
            raise NoDeploymentsError(
                f"No deployments matched filters. "
                f"Filters: flow_names={flow_names}, deployment_names={deployment_names}"
            )
        raise NoDeploymentsError("No deployments found in workspace.")

    # Get unique flow IDs and work pool names
    flow_ids: set[str] = set()
    work_pool_names: set[str] = set()

    for dep in deployment_responses:
        flow_ids.add(str(dep.flow_id))
        if dep.work_pool_name:
            work_pool_names.add(dep.work_pool_name)

    # Fetch flow names and work pools in parallel
    flow_names_task = _fetch_flows_for_deployments(client, flow_ids)
    work_pools_task = _fetch_work_pools_parallel(client, work_pool_names)

    (flow_id_to_name, flow_warnings), (work_pools, wp_warnings) = await asyncio.gather(
        flow_names_task, work_pools_task
    )
    warnings.extend(flow_warnings)
    warnings.extend(wp_warnings)

    # Group deployments by flow
    flows: dict[str, FlowInfo] = {}

    # Track short name -> full names mapping to detect ambiguity
    short_name_matches: dict[str, list[str]] = {}  # short_name -> list of full_names

    for dep in deployment_responses:
        flow_id = str(dep.flow_id)
        flow_name = flow_id_to_name.get(flow_id)

        if not flow_name:
            errors.append(
                f"Could not find flow name for deployment '{dep.name}' "
                f"(flow_id={flow_id}) - skipping"
            )
            continue

        # If filtering by deployment name, check the full name matches
        full_name = f"{flow_name}/{dep.name}"
        if deployment_names and full_name not in deployment_names:
            # Only include if the full name matches (filter was by name parts)
            # Skip if user specified full names and this doesn't match
            found_match = False
            matched_short_name: str | None = None
            for dn in deployment_names:
                if "/" not in dn:
                    # User gave just deployment name, check against dep.name
                    if dep.name == dn:
                        found_match = True
                        matched_short_name = dn
                        break
                else:
                    # User gave full name, must match exactly
                    if full_name == dn:
                        found_match = True
                        break
            if not found_match:
                continue
            # Track short name matches for ambiguity warning
            if matched_short_name:
                if matched_short_name not in short_name_matches:
                    short_name_matches[matched_short_name] = []
                short_name_matches[matched_short_name].append(full_name)

        # Create DeploymentInfo
        deployment_info = DeploymentInfo(
            name=dep.name,
            flow_name=flow_name,
            full_name=full_name,
            parameter_schema=dep.parameter_openapi_schema,
            work_pool_name=dep.work_pool_name,
            description=dep.description,
        )

        # Add to flow
        if flow_name not in flows:
            flows[flow_name] = FlowInfo(name=flow_name, deployments=[])
        flows[flow_name].deployments.append(deployment_info)

    if not flows:
        if flow_names or deployment_names:
            raise NoDeploymentsError(
                f"No deployments matched filters after processing. "
                f"Filters: flow_names={flow_names}, deployment_names={deployment_names}"
            )
        raise NoDeploymentsError("No deployments could be processed.")

    # Warn about ambiguous short names that matched multiple flows
    for short_name, full_names in short_name_matches.items():
        if len(full_names) > 1:
            warnings.append(
                f"Short deployment name '{short_name}' matched {len(full_names)} "
                f"deployments across different flows: {', '.join(sorted(full_names))}. "
                f"Consider using full names (flow/deployment) for precise filtering."
            )

    # Build metadata - prefer client.api_url, fall back to setting for provenance
    client_api_url = getattr(client, "api_url", None)
    api_url = str(client_api_url) if client_api_url else get_current_settings().api.url

    metadata = SDKGenerationMetadata(
        generation_time=datetime.now(timezone.utc).isoformat(),
        prefect_version=prefect.__version__,
        workspace_name=None,  # Could be extracted from Cloud API URL if needed
        api_url=api_url,
    )

    # Build final SDK data
    sdk_data = SDKData(
        metadata=metadata,
        flows=flows,
        work_pools=work_pools,
    )

    return FetchResult(
        data=sdk_data,
        warnings=warnings,
        errors=errors,
    )
