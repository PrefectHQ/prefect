"""
SDK generator module.

This module orchestrates the SDK generation process, combining data fetching
from the Prefect API with template rendering to produce the final SDK file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from prefect._sdk.fetcher import (
    APIConnectionError,
    AuthenticationError,
    FetchResult,
    NoDeploymentsError,
    SDKFetcherError,
    fetch_sdk_data,
)
from prefect._sdk.renderer import RenderResult, render_sdk

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


@dataclass
class GenerationResult:
    """Result of SDK generation.

    Attributes:
        output_path: Path to the generated SDK file.
        flow_count: Number of flows included in the SDK.
        deployment_count: Number of deployments included in the SDK.
        work_pool_count: Number of work pools included in the SDK.
        warnings: List of warnings encountered during generation.
        errors: List of non-fatal errors encountered during generation.
    """

    output_path: Path
    flow_count: int
    deployment_count: int
    work_pool_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SDKGeneratorError(Exception):
    """Base exception for SDK generator errors."""

    pass


# Re-export fetcher exceptions for convenience
__all__ = [
    "GenerationResult",
    "SDKGeneratorError",
    "AuthenticationError",
    "APIConnectionError",
    "NoDeploymentsError",
    "SDKFetcherError",
    "generate_sdk",
]


async def generate_sdk(
    client: "PrefectClient",
    output_path: Path,
    flow_names: list[str] | None = None,
    deployment_names: list[str] | None = None,
) -> GenerationResult:
    """Generate a typed SDK from workspace deployments.

    This is the main entry point for SDK generation. It fetches deployment
    and work pool data from the Prefect API, then renders a typed Python
    SDK file.

    Args:
        client: An active Prefect client (must be entered as context manager).
        output_path: Path where the SDK file should be written.
        flow_names: Optional list of flow names to filter to.
        deployment_names: Optional list of deployment names to filter to.
            These should be in "flow-name/deployment-name" format.

    Returns:
        GenerationResult with statistics and any warnings/errors.

    Raises:
        AuthenticationError: If not authenticated with Prefect.
        APIConnectionError: If the Prefect API cannot be reached.
        NoDeploymentsError: If no deployments match the filters.
        SDKGeneratorError: For other generation errors.

    Example:
        ```python
        from prefect.client.orchestration import get_client
        from prefect._sdk.generator import generate_sdk
        from pathlib import Path

        async with get_client() as client:
            result = await generate_sdk(
                client=client,
                output_path=Path("my_sdk.py"),
                flow_names=["my-etl-flow"],
            )
            print(f"Generated SDK with {result.deployment_count} deployments")
        ```
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Fetch data from API
    fetch_result: FetchResult = await fetch_sdk_data(
        client=client,
        flow_names=flow_names,
        deployment_names=deployment_names,
    )

    warnings.extend(fetch_result.warnings)
    errors.extend(fetch_result.errors)

    # Render SDK to file
    try:
        render_result: RenderResult = render_sdk(
            data=fetch_result.data,
            output_path=output_path,
        )
        warnings.extend(render_result.warnings)
    except Exception as e:
        raise SDKGeneratorError(f"Failed to render SDK: {e}") from e

    # Collect statistics
    sdk_data = fetch_result.data

    return GenerationResult(
        output_path=output_path,
        flow_count=sdk_data.flow_count,
        deployment_count=sdk_data.deployment_count,
        work_pool_count=sdk_data.work_pool_count,
        warnings=warnings,
        errors=errors,
    )
