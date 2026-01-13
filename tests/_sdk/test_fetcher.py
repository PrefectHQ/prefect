"""Tests for the SDK fetcher module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from prefect._sdk.fetcher import (
    APIConnectionError,
    AuthenticationError,
    FetchResult,
    NoDeploymentsError,
    _check_authentication,
    _fetch_deployments,
    _fetch_flows_for_deployments,
    _fetch_work_pool,
    _fetch_work_pools_parallel,
    fetch_sdk_data,
)
from prefect.client.schemas.filters import FlowFilter, FlowFilterName
from prefect.exceptions import ObjectNotFound


def make_deployment_response(
    name: str,
    flow_id: UUID | None = None,
    work_pool_name: str | None = None,
    parameter_schema: dict[str, Any] | None = None,
    description: str | None = None,
) -> MagicMock:
    """Create a mock DeploymentResponse."""
    dep = MagicMock()
    dep.name = name
    dep.flow_id = flow_id or uuid4()
    dep.work_pool_name = work_pool_name
    dep.parameter_openapi_schema = parameter_schema
    dep.description = description
    return dep


def make_flow_response(name: str, flow_id: UUID | None = None) -> MagicMock:
    """Create a mock Flow response."""
    flow = MagicMock()
    flow.name = name
    flow.id = flow_id or uuid4()
    return flow


def make_work_pool_response(
    name: str,
    pool_type: str = "kubernetes",
    base_job_template: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock WorkPool response."""
    wp = MagicMock()
    wp.name = name
    wp.type = pool_type
    wp.base_job_template = base_job_template or {}
    return wp


class TestCheckAuthentication:
    """Tests for _check_authentication."""

    async def test_authentication_success(self) -> None:
        """Successful authentication check passes silently."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(return_value=None)

        await _check_authentication(client)  # Should not raise

    async def test_authentication_failure_unauthorized(self) -> None:
        """Unauthorized error raises AuthenticationError."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(
            return_value=Exception("401 Unauthorized: Invalid API key")
        )
        client.api_url = "https://api.prefect.cloud"

        with pytest.raises(AuthenticationError) as exc_info:
            await _check_authentication(client)

        assert "Not authenticated" in str(exc_info.value)

    async def test_authentication_failure_connection_error(self) -> None:
        """Connection error raises APIConnectionError."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(return_value=Exception("Connection refused"))
        client.api_url = "https://localhost:4200"

        with pytest.raises(APIConnectionError) as exc_info:
            await _check_authentication(client)

        assert "Could not connect" in str(exc_info.value)

    async def test_authentication_failure_exception(self) -> None:
        """Exception during healthcheck raises APIConnectionError."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(side_effect=RuntimeError("Network error"))
        client.api_url = "https://api.prefect.cloud"

        with pytest.raises(APIConnectionError) as exc_info:
            await _check_authentication(client)

        assert "Could not connect" in str(exc_info.value)


class TestFetchDeployments:
    """Tests for _fetch_deployments."""

    async def test_fetch_single_page(self) -> None:
        """Fetches single page of deployments."""
        client = AsyncMock()
        deps = [make_deployment_response(f"dep-{i}") for i in range(5)]
        client.read_deployments = AsyncMock(return_value=deps)

        result = await _fetch_deployments(client)

        assert len(result) == 5
        client.read_deployments.assert_called_once()

    async def test_fetch_multiple_pages(self) -> None:
        """Fetches multiple pages of deployments."""
        client = AsyncMock()

        # First call returns 200 items (full page), second returns 50 (partial page)
        # Pagination stops when page is not full
        page1 = [make_deployment_response(f"dep-{i}") for i in range(200)]
        page2 = [make_deployment_response(f"dep-{i}") for i in range(200, 250)]

        client.read_deployments = AsyncMock(side_effect=[page1, page2])

        result = await _fetch_deployments(client)

        assert len(result) == 250
        # Two calls: first returns full page (200), second returns partial (50)
        assert client.read_deployments.call_count == 2

    async def test_fetch_with_filters(self) -> None:
        """Passes filters to the API."""
        client = AsyncMock()
        client.read_deployments = AsyncMock(return_value=[])

        flow_filter = FlowFilter(name=FlowFilterName(any_=["my-flow"]))

        await _fetch_deployments(client, flow_filter=flow_filter)

        call_kwargs = client.read_deployments.call_args.kwargs
        assert call_kwargs["flow_filter"] == flow_filter

    async def test_fetch_empty(self) -> None:
        """Returns empty list when no deployments."""
        client = AsyncMock()
        client.read_deployments = AsyncMock(return_value=[])

        result = await _fetch_deployments(client)

        assert result == []


class TestFetchWorkPool:
    """Tests for _fetch_work_pool."""

    async def test_fetch_work_pool_success(self) -> None:
        """Successfully fetches a work pool."""
        client = AsyncMock()
        wp = make_work_pool_response(
            "my-pool",
            pool_type="kubernetes",
            base_job_template={
                "variables": {
                    "type": "object",
                    "properties": {
                        "image": {"type": "string"},
                        "cpu": {"type": "string"},
                    },
                }
            },
        )
        client.read_work_pool = AsyncMock(return_value=wp)

        result = await _fetch_work_pool(client, "my-pool")

        assert result is not None
        assert result.name == "my-pool"
        assert result.pool_type == "kubernetes"
        assert "properties" in result.job_variables_schema

    async def test_fetch_work_pool_not_found(self) -> None:
        """Returns None when work pool not found."""
        client = AsyncMock()
        client.read_work_pool = AsyncMock(side_effect=ObjectNotFound("Not found"))

        result = await _fetch_work_pool(client, "missing-pool")

        assert result is None

    async def test_fetch_work_pool_error_propagates(self) -> None:
        """Non-ObjectNotFound errors propagate for gather to capture."""
        client = AsyncMock()
        client.read_work_pool = AsyncMock(side_effect=RuntimeError("API error"))

        # Error should propagate (not return None)
        with pytest.raises(RuntimeError, match="API error"):
            await _fetch_work_pool(client, "error-pool")

    async def test_fetch_work_pool_empty_template(self) -> None:
        """Handles work pool with empty base_job_template."""
        client = AsyncMock()
        wp = make_work_pool_response("my-pool", base_job_template={})
        client.read_work_pool = AsyncMock(return_value=wp)

        result = await _fetch_work_pool(client, "my-pool")

        assert result is not None
        assert result.job_variables_schema == {}


class TestFetchWorkPoolsParallel:
    """Tests for _fetch_work_pools_parallel."""

    async def test_fetch_multiple_pools_parallel(self) -> None:
        """Fetches multiple work pools in parallel."""
        client = AsyncMock()

        async def mock_read_pool(name: str) -> MagicMock:
            return make_work_pool_response(name)

        client.read_work_pool = mock_read_pool

        pools, warnings = await _fetch_work_pools_parallel(
            client, {"pool-1", "pool-2", "pool-3"}
        )

        assert len(pools) == 3
        assert "pool-1" in pools
        assert "pool-2" in pools
        assert "pool-3" in pools
        assert warnings == []

    async def test_fetch_pools_with_missing(self) -> None:
        """Handles missing work pools with warnings."""
        client = AsyncMock()

        async def mock_read_pool(name: str) -> MagicMock:
            if name == "missing":
                raise ObjectNotFound("Not found")
            return make_work_pool_response(name)

        client.read_work_pool = mock_read_pool

        pools, warnings = await _fetch_work_pools_parallel(
            client, {"good-pool", "missing"}
        )

        assert len(pools) == 1
        assert "good-pool" in pools
        assert len(warnings) == 1
        assert "missing" in warnings[0]

    async def test_fetch_pools_empty_set(self) -> None:
        """Returns empty results for empty input."""
        client = AsyncMock()

        pools, warnings = await _fetch_work_pools_parallel(client, set())

        assert pools == {}
        assert warnings == []


class TestFetchFlowsForDeployments:
    """Tests for _fetch_flows_for_deployments."""

    async def test_fetch_flows_success(self) -> None:
        """Successfully fetches flow names."""
        client = AsyncMock()
        flow_id = uuid4()
        flow = make_flow_response("my-flow", flow_id)
        client.read_flows = AsyncMock(return_value=[flow])

        result, warnings = await _fetch_flows_for_deployments(client, {str(flow_id)})

        assert str(flow_id) in result
        assert result[str(flow_id)] == "my-flow"
        assert warnings == []

    async def test_fetch_flows_empty(self) -> None:
        """Returns empty dict for empty input."""
        client = AsyncMock()

        result, warnings = await _fetch_flows_for_deployments(client, set())

        assert result == {}
        assert warnings == []

    async def test_fetch_flows_invalid_uuid(self) -> None:
        """Handles invalid UUID strings with warning."""
        client = AsyncMock()
        valid_id = uuid4()
        flow = make_flow_response("my-flow", valid_id)
        client.read_flows = AsyncMock(return_value=[flow])

        result, warnings = await _fetch_flows_for_deployments(
            client, {str(valid_id), "not-a-uuid", "also-invalid"}
        )

        # Valid UUID should still be fetched
        assert str(valid_id) in result
        # Invalid UUIDs should generate warnings
        assert len(warnings) == 2
        assert any("not-a-uuid" in w for w in warnings)
        assert any("also-invalid" in w for w in warnings)


class TestFetchSDKData:
    """Tests for fetch_sdk_data main function."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock client with basic setup."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(return_value=None)
        client.api_url = "https://api.prefect.cloud"
        return client

    async def test_fetch_sdk_data_success(self, mock_client: AsyncMock) -> None:
        """Successfully fetches SDK data."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="k8s-pool",
            parameter_schema={"type": "object", "properties": {}},
        )
        flow = make_flow_response("my-flow", flow_id)
        wp = make_work_pool_response(
            "k8s-pool",
            base_job_template={"variables": {"type": "object", "properties": {}}},
        )

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(return_value=wp)

        result = await fetch_sdk_data(mock_client)

        assert isinstance(result, FetchResult)
        assert result.data.flow_count == 1
        assert result.data.deployment_count == 1
        assert result.data.work_pool_count == 1
        assert "my-flow" in result.data.flows
        assert len(result.data.flows["my-flow"].deployments) == 1
        assert result.data.flows["my-flow"].deployments[0].name == "production"

    async def test_fetch_sdk_data_no_deployments(self, mock_client: AsyncMock) -> None:
        """Raises NoDeploymentsError when no deployments found."""
        mock_client.read_deployments = AsyncMock(return_value=[])

        with pytest.raises(NoDeploymentsError) as exc_info:
            await fetch_sdk_data(mock_client)

        assert "No deployments found" in str(exc_info.value)

    async def test_fetch_sdk_data_filter_no_match(self, mock_client: AsyncMock) -> None:
        """Raises NoDeploymentsError when filters don't match."""
        mock_client.read_deployments = AsyncMock(return_value=[])

        with pytest.raises(NoDeploymentsError) as exc_info:
            await fetch_sdk_data(mock_client, flow_names=["nonexistent-flow"])

        assert "No deployments matched filters" in str(exc_info.value)

    async def test_fetch_sdk_data_with_flow_filter(
        self, mock_client: AsyncMock
    ) -> None:
        """Applies flow name filter."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        await fetch_sdk_data(mock_client, flow_names=["my-flow"])

        call_kwargs = mock_client.read_deployments.call_args.kwargs
        assert call_kwargs["flow_filter"] is not None

    async def test_fetch_sdk_data_with_deployment_filter(
        self, mock_client: AsyncMock
    ) -> None:
        """Applies deployment name filter."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        await fetch_sdk_data(mock_client, deployment_names=["my-flow/production"])

        call_kwargs = mock_client.read_deployments.call_args.kwargs
        assert call_kwargs["deployment_filter"] is not None

    async def test_fetch_sdk_data_missing_work_pool(
        self, mock_client: AsyncMock
    ) -> None:
        """Handles missing work pool with warning."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="missing-pool",
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(side_effect=ObjectNotFound("Not found"))

        result = await fetch_sdk_data(mock_client)

        assert len(result.warnings) >= 1
        assert any("missing-pool" in w for w in result.warnings)

    async def test_fetch_sdk_data_multiple_deployments_same_flow(
        self, mock_client: AsyncMock
    ) -> None:
        """Groups multiple deployments under same flow."""
        flow_id = uuid4()
        dep1 = make_deployment_response("production", flow_id=flow_id)
        dep2 = make_deployment_response("staging", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep1, dep2])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await fetch_sdk_data(mock_client)

        assert result.data.flow_count == 1
        assert result.data.deployment_count == 2
        assert len(result.data.flows["my-flow"].deployments) == 2

    async def test_fetch_sdk_data_multiple_flows(self, mock_client: AsyncMock) -> None:
        """Handles deployments from multiple flows."""
        flow_id1 = uuid4()
        flow_id2 = uuid4()
        dep1 = make_deployment_response("production", flow_id=flow_id1)
        dep2 = make_deployment_response("daily", flow_id=flow_id2)
        flow1 = make_flow_response("etl-flow", flow_id1)
        flow2 = make_flow_response("sync-flow", flow_id2)

        mock_client.read_deployments = AsyncMock(return_value=[dep1, dep2])
        mock_client.read_flows = AsyncMock(return_value=[flow1, flow2])

        result = await fetch_sdk_data(mock_client)

        assert result.data.flow_count == 2
        assert result.data.deployment_count == 2
        assert "etl-flow" in result.data.flows
        assert "sync-flow" in result.data.flows

    async def test_fetch_sdk_data_auth_error(self, mock_client: AsyncMock) -> None:
        """Raises AuthenticationError on auth failure."""
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("401 Unauthorized")
        )

        with pytest.raises(AuthenticationError):
            await fetch_sdk_data(mock_client)

    async def test_fetch_sdk_data_connection_error(
        self, mock_client: AsyncMock
    ) -> None:
        """Raises APIConnectionError on connection failure."""
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("Connection refused")
        )

        with pytest.raises(APIConnectionError):
            await fetch_sdk_data(mock_client)

    async def test_fetch_sdk_data_metadata(self, mock_client: AsyncMock) -> None:
        """Generates correct metadata."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await fetch_sdk_data(mock_client)

        assert result.data.metadata.generation_time is not None
        assert result.data.metadata.prefect_version is not None

    async def test_fetch_sdk_data_metadata_uses_client_api_url(
        self, mock_client: AsyncMock
    ) -> None:
        """Metadata api_url comes from client.api_url."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.api_url = "https://custom.prefect.cloud/api"

        result = await fetch_sdk_data(mock_client)

        assert result.data.metadata.api_url == "https://custom.prefect.cloud/api"

    async def test_fetch_sdk_data_work_pool_warning_mentions_with_infra(
        self, mock_client: AsyncMock
    ) -> None:
        """Work pool warning mentions with_infra() will not be generated."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="missing-pool",
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(side_effect=ObjectNotFound("Not found"))

        result = await fetch_sdk_data(mock_client)

        assert any("with_infra()" in w for w in result.warnings)

    async def test_fetch_sdk_data_work_pool_error_includes_exception(
        self, mock_client: AsyncMock
    ) -> None:
        """Work pool fetch error includes exception details in warning."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="error-pool",
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(
            side_effect=RuntimeError("Connection timeout")
        )

        result = await fetch_sdk_data(mock_client)

        # Warning should include the exception text
        assert any("Connection timeout" in w for w in result.warnings)
        assert any("error-pool" in w for w in result.warnings)

    async def test_fetch_sdk_data_ambiguous_short_name_warning(
        self, mock_client: AsyncMock
    ) -> None:
        """Warns when short deployment name matches multiple flows."""
        flow_id1 = uuid4()
        flow_id2 = uuid4()
        # "production" deployment in two different flows
        dep1 = make_deployment_response("production", flow_id=flow_id1)
        dep2 = make_deployment_response("production", flow_id=flow_id2)
        flow1 = make_flow_response("etl-flow", flow_id1)
        flow2 = make_flow_response("sync-flow", flow_id2)

        mock_client.read_deployments = AsyncMock(return_value=[dep1, dep2])
        mock_client.read_flows = AsyncMock(return_value=[flow1, flow2])

        # Filter with just short name "production"
        result = await fetch_sdk_data(mock_client, deployment_names=["production"])

        # Should warn about ambiguous short name
        assert any("Short deployment name 'production'" in w for w in result.warnings)
        assert any("Consider using full names" in w for w in result.warnings)
        # Both deployments should still be included
        assert result.data.deployment_count == 2
