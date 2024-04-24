"""
Tests for the server-side orchestration API client, used by server-side services to
interact with the Prefect API.
"""

from typing import TYPE_CHECKING, AsyncGenerator, List
from unittest import mock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.api.clients import OrchestrationClient
from prefect.server.models.variables import create_variable
from prefect.server.schemas.actions import VariableCreate
from prefect.server.schemas.responses import DeploymentResponse

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMDeployment, ORMVariable


@pytest.fixture
async def orchestration_client() -> AsyncGenerator[OrchestrationClient, None]:
    async with OrchestrationClient() as client:
        yield client


async def test_read_deployment(
    deployment: "ORMDeployment", orchestration_client: OrchestrationClient
):
    from_api = await orchestration_client.read_deployment(deployment.id)
    assert isinstance(from_api, DeploymentResponse)

    assert from_api.id == deployment.id
    assert from_api.name == deployment.name


async def test_read_deployment_not_found(orchestration_client: OrchestrationClient):
    from_api = await orchestration_client.read_deployment(uuid4())
    assert from_api is None


async def test_read_deployment_raises_errors(orchestration_client: OrchestrationClient):
    with mock.patch(
        "prefect.server.api.deployments.models.deployments.read_deployment",
        return_value=ValueError("woops"),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await orchestration_client.read_deployment(uuid4())


@pytest.fixture
async def variables(
    session: AsyncSession,
):
    variables = [
        VariableCreate(name="variable1", value="value1", tags=["tag1"]),
        VariableCreate(name="variable12", value="value12", tags=["tag2"]),
        VariableCreate(name="variable2", value="value2", tags=["tag1"]),
        VariableCreate(name="variable21", value="value21", tags=["tag2"]),
    ]
    models = []
    for variable in variables:
        model = await create_variable(session, variable)
        models.append(model)
    await session.commit()

    return models


async def test_read_variables(
    variables: List["ORMVariable"],
    orchestration_client: OrchestrationClient,
):
    from_api = await orchestration_client.read_workspace_variables()
    assert from_api == {
        "variable1": "value1",
        "variable12": "value12",
        "variable2": "value2",
        "variable21": "value21",
    }


async def test_read_variables_across_pages(
    variables: List["ORMVariable"],
    orchestration_client: OrchestrationClient,
):
    orchestration_client.VARIABLE_PAGE_SIZE = 3
    from_api = await orchestration_client.read_workspace_variables()
    assert from_api == {
        "variable1": "value1",
        "variable12": "value12",
        "variable2": "value2",
        "variable21": "value21",
    }


async def test_read_variables_subset(
    variables: List["ORMVariable"],
    orchestration_client: OrchestrationClient,
):
    orchestration_client.VARIABLE_PAGE_SIZE = 3
    from_api = await orchestration_client.read_workspace_variables(
        names=["variable1", "variable12"]
    )
    assert from_api == {
        "variable1": "value1",
        "variable12": "value12",
    }


async def test_read_variables_empty(
    orchestration_client: OrchestrationClient,
):
    from_api = await orchestration_client.read_workspace_variables()
    assert from_api == {}


async def test_read_variables_subset_none_requested(
    variables: List["ORMVariable"],
    orchestration_client: OrchestrationClient,
):
    from_api = await orchestration_client.read_workspace_variables(names=[])
    assert from_api == {}


async def test_read_variables_empty_nonsensical_maximum(
    orchestration_client: OrchestrationClient,
):
    orchestration_client.MAX_VARIABLES_PER_WORKSPACE = 0
    from_api = await orchestration_client.read_workspace_variables()
    assert from_api == {}


async def test_read_variables_with_error(orchestration_client: OrchestrationClient):
    with mock.patch(
        "prefect.server.api.variables.models.variables.read_variables",
        return_value=ValueError("woops"),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await orchestration_client.read_workspace_variables()
