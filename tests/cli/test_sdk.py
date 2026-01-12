"""Tests for the SDK CLI command."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prefect.testing.cli import invoke_and_assert


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


class TestSDKGenerate:
    """Tests for the prefect sdk generate command."""

    def test_sdk_generate_help(self) -> None:
        """Shows help text."""
        invoke_and_assert(
            ["sdk", "generate", "--help"],
            expected_output_contains=[
                "Generate a typed Python SDK",
                "--output",
                "--flow",
                "--deployment",
            ],
            expected_code=0,
        )

    def test_sdk_generate_requires_output(self) -> None:
        """Requires --output option."""
        invoke_and_assert(
            ["sdk", "generate"],
            expected_output_contains="--output",
            expected_code=2,  # Typer exit code for missing required option
        )

    def test_sdk_generate_basic(self, tmp_path: Path) -> None:
        """Generates SDK file successfully."""
        output_path = tmp_path / "my_sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                },
                "required": ["source"],
            },
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "SDK generated successfully",
                    "Flows:       1",
                    "Deployments: 1",
                    "from my_sdk import deployments",
                ],
                expected_code=0,
            )

        assert output_path.exists()
        code = output_path.read_text()
        ast.parse(code)  # Verify valid Python

    def test_sdk_generate_with_flow_filter(self, tmp_path: Path) -> None:
        """Accepts --flow filter option."""
        output_path = tmp_path / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                [
                    "sdk",
                    "generate",
                    "--output",
                    str(output_path),
                    "--flow",
                    "my-flow",
                ],
                expected_output_contains="SDK generated successfully",
                expected_code=0,
            )

    def test_sdk_generate_with_deployment_filter(self, tmp_path: Path) -> None:
        """Accepts --deployment filter option."""
        output_path = tmp_path / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                [
                    "sdk",
                    "generate",
                    "--output",
                    str(output_path),
                    "--deployment",
                    "my-flow/production",
                ],
                expected_output_contains="SDK generated successfully",
                expected_code=0,
            )

    def test_sdk_generate_with_multiple_filters(self, tmp_path: Path) -> None:
        """Accepts multiple --flow and --deployment options."""
        output_path = tmp_path / "sdk.py"

        flow_id1 = uuid4()
        flow_id2 = uuid4()
        deps = [
            make_deployment_response("prod", flow_id=flow_id1),
            make_deployment_response("staging", flow_id=flow_id2),
        ]
        flows = [
            make_flow_response("flow-a", flow_id1),
            make_flow_response("flow-b", flow_id2),
        ]

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=deps)
        mock_client.read_flows = AsyncMock(return_value=flows)

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                [
                    "sdk",
                    "generate",
                    "--output",
                    str(output_path),
                    "--flow",
                    "flow-a",
                    "--flow",
                    "flow-b",
                ],
                expected_output_contains=[
                    "SDK generated successfully",
                    "Flows:       2",
                ],
                expected_code=0,
            )

    def test_sdk_generate_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates parent directories if they don't exist."""
        output_path = tmp_path / "subdir" / "nested" / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="SDK generated successfully",
                expected_code=0,
            )

        assert output_path.exists()

    def test_sdk_generate_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Overwrites existing file without prompting."""
        output_path = tmp_path / "sdk.py"
        output_path.write_text("# old content")

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="SDK generated successfully",
                expected_code=0,
            )

        code = output_path.read_text()
        assert "# old content" not in code
        assert "Prefect SDK" in code

    def test_sdk_generate_displays_warnings(self, tmp_path: Path) -> None:
        """Displays warnings from generation."""
        output_path = tmp_path / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response(
            "production",
            flow_id=flow_id,
            work_pool_name="missing-pool",
        )
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        from prefect.exceptions import ObjectNotFound

        mock_client.read_work_pool = AsyncMock(
            side_effect=ObjectNotFound(Exception("Not found"))
        )

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "Warning:",
                    "missing-pool",
                    "SDK generated successfully",
                ],
                expected_code=0,
            )

    def test_sdk_generate_auth_error(self, tmp_path: Path) -> None:
        """Displays error message on authentication failure."""
        output_path = tmp_path / "sdk.py"

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("401 Unauthorized")
        )
        mock_client.api_url = "https://api.prefect.cloud"

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="Not authenticated",
                expected_code=1,
            )

    def test_sdk_generate_connection_error(self, tmp_path: Path) -> None:
        """Displays error message on connection failure."""
        output_path = tmp_path / "sdk.py"

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(
            return_value=Exception("Connection refused")
        )
        mock_client.api_url = "https://api.prefect.cloud"

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="Could not connect to Prefect API",
                expected_code=1,
            )

    def test_sdk_generate_no_deployments(self, tmp_path: Path) -> None:
        """Displays error message when no deployments found."""
        output_path = tmp_path / "sdk.py"

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "No deployments found",
                    "prefect deploy",
                ],
                expected_code=1,
            )

    def test_sdk_generate_shows_fetching_message(self, tmp_path: Path) -> None:
        """Shows 'Fetching deployments...' progress message."""
        output_path = tmp_path / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="Fetching deployments",
                expected_code=0,
            )

    def test_sdk_generate_shows_output_path(self, tmp_path: Path) -> None:
        """Shows the output path in the success message."""
        output_path = tmp_path / "my_custom_sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "Output:",
                    "my_custom_sdk.py",
                ],
                expected_code=0,
            )

    def test_sdk_generate_with_work_pools(self, tmp_path: Path) -> None:
        """Shows work pool count in statistics."""
        output_path = tmp_path / "sdk.py"

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
                    },
                }
            },
        )

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])
        mock_client.read_work_pool = AsyncMock(return_value=wp)

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "Work pools:  1",
                ],
                expected_code=0,
            )

    def test_sdk_generate_render_failure(self, tmp_path: Path) -> None:
        """Displays error message on render failure."""
        output_path = tmp_path / "sdk.py"

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with (
            patch(
                "prefect.cli.sdk.get_client",
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
            ),
            patch(
                "prefect._sdk.generator.render_sdk",
                side_effect=Exception("Template rendering failed"),
            ),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains="SDK generation failed",
                expected_code=1,
            )

    def test_sdk_generate_invalid_module_name(self, tmp_path: Path) -> None:
        """Shows rename hint when filename is not a valid Python identifier."""
        output_path = tmp_path / "my-sdk.py"  # Dash makes it invalid

        flow_id = uuid4()
        dep = make_deployment_response("production", flow_id=flow_id)
        flow = make_flow_response("my-flow", flow_id)

        mock_client = AsyncMock()
        mock_client.api_healthcheck = AsyncMock(return_value=None)
        mock_client.api_url = "https://api.prefect.cloud"
        mock_client.read_deployments = AsyncMock(return_value=[dep])
        mock_client.read_flows = AsyncMock(return_value=[flow])

        with patch(
            "prefect.cli.sdk.get_client",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)),
        ):
            invoke_and_assert(
                ["sdk", "generate", "--output", str(output_path)],
                expected_output_contains=[
                    "SDK generated successfully",
                    "my-sdk",
                    "not a valid Python module name",
                    "Rename the file to",
                    "my_sdk.py",
                ],
                expected_output_does_not_contain="from my-sdk import",
                expected_code=0,
            )

    def test_sdk_generate_directory_as_output(self, tmp_path: Path) -> None:
        """Shows clear error when output is a directory."""
        output_path = tmp_path / "subdir"
        output_path.mkdir()  # Create directory

        # No mocking needed - error is caught before API calls
        invoke_and_assert(
            ["sdk", "generate", "--output", str(output_path)],
            expected_output_contains=[
                "is a directory",
                "Please provide a file path",
            ],
            expected_code=1,
        )


class TestSDKHelp:
    """Tests for the sdk command group help."""

    def test_sdk_help(self) -> None:
        """Shows help for sdk command group."""
        invoke_and_assert(
            ["sdk", "--help"],
            expected_output_contains=[
                "sdk",
                "generate",
            ],
            expected_code=0,
        )
