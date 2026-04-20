"""Tests for the SDK generator module."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prefect._sdk.generator import (
    APIConnectionError,
    AuthenticationError,
    GenerationResult,
    NoDeploymentsError,
    generate_sdk,
)
from prefect.exceptions import ObjectNotFound


def make_deployment_response(
    name: str,
    flow_id: Any = None,
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


def make_flow_response(name: str, flow_id: Any = None) -> MagicMock:
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


class TestGenerateSDK:
    """Tests for the generate_sdk function."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock Prefect client."""
        client = AsyncMock()
        client.api_healthcheck = AsyncMock(return_value=None)
        client.api_url = "https://api.prefect.cloud"
        return client

    @pytest.fixture
    def output_path(self, tmp_path: Path) -> Path:
        """Create a temporary output path."""
        return tmp_path / "my_sdk.py"

    async def test_generate_sdk_basic(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Generates a valid SDK file."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "count": {"type": "integer", "default": 10},
                },
                "required": ["source"],
            },
        )
        flow = make_flow_response("my-etl-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await generate_sdk(mock_client, output_path)

        assert isinstance(result, GenerationResult)
        assert result.output_path == output_path
        assert result.flow_count == 1
        assert result.deployment_count == 1
        assert result.work_pool_count == 0
        assert output_path.exists()

        # Verify generated code is valid Python
        code = output_path.read_text()
        ast.parse(code)

    async def test_generate_sdk_with_work_pool(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Generates SDK with work pool job variables."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="k8s-pool",
        )
        flow = make_flow_response("my-flow", flow_id)
        wp = make_work_pool_response(
            "k8s-pool",
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

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(return_value=wp)

        result = await generate_sdk(mock_client, output_path)

        assert result.work_pool_count == 1

        code = output_path.read_text()
        assert "K8SPoolJobVariables" in code or "K8sPoolJobVariables" in code

    async def test_generate_sdk_with_flow_filter(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Passes flow filter to fetcher."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await generate_sdk(mock_client, output_path, flow_names=["my-flow"])

        assert result.flow_count == 1

    async def test_generate_sdk_with_deployment_filter(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Passes deployment filter to fetcher."""
        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await generate_sdk(
            mock_client, output_path, deployment_names=["my-flow/production"]
        )

        assert result.deployment_count == 1

    async def test_generate_sdk_creates_parent_directories(
        self, mock_client: AsyncMock, tmp_path: Path
    ) -> None:
        """Creates parent directories if they don't exist."""
        output_path = tmp_path / "subdir" / "nested" / "my_sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        result = await generate_sdk(mock_client, output_path)

        assert output_path.exists()
        assert result.output_path == output_path

    async def test_generate_sdk_overwrites_existing(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Overwrites existing file."""
        output_path.write_text("# old content")

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        await generate_sdk(mock_client, output_path)

        code = output_path.read_text()
        assert "# old content" not in code
        assert "Prefect SDK" in code

    async def test_generate_sdk_collects_warnings(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Collects warnings from fetcher."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="missing-pool",
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        # Simulate work pool not found
        mock_client.read_work_pool = AsyncMock(side_effect=ObjectNotFound("Not found"))

        result = await generate_sdk(mock_client, output_path)

        assert len(result.warnings) >= 1
        assert any("missing-pool" in w for w in result.warnings)

    async def test_generate_sdk_auth_error(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Raises AuthenticationError on auth failure."""
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("401 Unauthorized")
        )

        with pytest.raises(AuthenticationError):
            await generate_sdk(mock_client, output_path)

    async def test_generate_sdk_connection_error(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Raises APIConnectionError on connection failure."""
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("Connection refused")
        )

        with pytest.raises(APIConnectionError):
            await generate_sdk(mock_client, output_path)

    async def test_generate_sdk_no_deployments(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Raises NoDeploymentsError when no deployments found."""
        mock_client.read_deployments = AsyncMock(return_value=[])

        with pytest.raises(NoDeploymentsError):
            await generate_sdk(mock_client, output_path)

    async def test_generate_sdk_multiple_deployments(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Handles multiple deployments across flows."""
        flow_id1 = uuid4()
        flow_id2 = uuid4()
        deps = [
            make_deployment_response("production", flow_id=flow_id1),
            make_deployment_response("staging", flow_id=flow_id1),
            make_deployment_response("daily", flow_id=flow_id2),
        ]
        flows = [
            make_flow_response("etl-flow", flow_id1),
            make_flow_response("sync-flow", flow_id2),
        ]

        mock_client.read_deployments = AsyncMock(return_value=deps)
        mock_client.read_flows = AsyncMock(return_value=flows)

        result = await generate_sdk(mock_client, output_path)

        assert result.flow_count == 2
        assert result.deployment_count == 3

        code = output_path.read_text()
        assert "etl-flow/production" in code
        assert "etl-flow/staging" in code
        assert "sync-flow/daily" in code

    async def test_generate_sdk_valid_python(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Generated code is valid Python."""
        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="k8s-pool",
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "batch_size": {"type": "integer", "default": 100},
                    "full_refresh": {"type": "boolean", "default": False},
                },
                "required": ["source"],
            },
            description="Production ETL deployment",
        )
        flow = make_flow_response("my-etl-flow", flow_id)
        wp = make_work_pool_response(
            "k8s-pool",
            base_job_template={
                "variables": {
                    "type": "object",
                    "properties": {
                        "image": {"type": "string"},
                        "cpu": {"type": "string"},
                        "memory": {"type": "string"},
                    },
                }
            },
        )

        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(return_value=wp)

        await generate_sdk(mock_client, output_path)

        code = output_path.read_text()

        # Verify valid Python
        ast.parse(code)

        # Verify expected content
        assert "deployments" in code
        assert "from_name" in code
        assert "my-etl-flow/production" in code
        assert "DeploymentName" in code

    async def test_generate_sdk_result_statistics(
        self, mock_client: AsyncMock, output_path: Path
    ) -> None:
        """Returns correct statistics in result."""
        flow_id1 = uuid4()
        flow_id2 = uuid4()
        deps = [
            make_deployment_response("prod", flow_id=flow_id1, work_pool_name="pool-1"),
            make_deployment_response(
                "stage", flow_id=flow_id1, work_pool_name="pool-2"
            ),
            make_deployment_response(
                "daily", flow_id=flow_id2, work_pool_name="pool-1"
            ),
        ]
        flows = [
            make_flow_response("flow-a", flow_id1),
            make_flow_response("flow-b", flow_id2),
        ]

        mock_client.read_deployments = AsyncMock(return_value=deps)
        mock_client.read_flows = AsyncMock(return_value=flows)
        mock_client.read_work_pool = AsyncMock(
            side_effect=lambda name: make_work_pool_response(
                name,
                base_job_template={
                    "variables": {
                        "type": "object",
                        "properties": {"x": {"type": "string"}},
                    }
                },
            )
        )

        result = await generate_sdk(mock_client, output_path)

        assert result.flow_count == 2
        assert result.deployment_count == 3
        assert result.work_pool_count == 2  # pool-1 and pool-2
