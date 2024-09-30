import uuid

import httpx
import pytest
import respx
from respx.patterns import M

from prefect.client.cloud import get_cloud_client
from prefect.settings import PREFECT_API_URL, PREFECT_UNIT_TEST_MODE, temporary_settings

mock_work_pool_types_response = {
    "prefect": {
        "prefect-agent": {
            "type": "prefect-agent",
            "default_base_job_configuration": {},
        }
    },
    "prefect-kubernetes": {
        "kubernetes": {
            "type": "kubernetes",
            "default_base_job_configuration": {},
        }
    },
}


@pytest.fixture
async def mock_work_pool_types():
    with respx.mock(
        assert_all_mocked=False, base_url=PREFECT_API_URL.value()
    ) as respx_mock:
        respx_mock.route(
            M(
                path__regex=(
                    r"accounts/(.{36})/workspaces/(.{36})/collections/work_pool_types"
                )
            ),
            method="GET",
        ).mock(
            return_value=httpx.Response(
                200,
                json=mock_work_pool_types_response,
            )
        )
        yield


async def test_cloud_client_init_with_no_api():
    with temporary_settings({PREFECT_API_URL: None}):
        async with get_cloud_client() as client:
            assert client


async def test_cloud_client_follow_redirects():
    httpx_settings = {"follow_redirects": True}
    async with get_cloud_client(httpx_settings=httpx_settings) as client:
        assert client._client.follow_redirects is True

    httpx_settings = {"follow_redirects": False}
    async with get_cloud_client(httpx_settings=httpx_settings) as client:
        assert client._client.follow_redirects is False

    # follow redirects by default
    with temporary_settings({PREFECT_UNIT_TEST_MODE: False}):
        async with get_cloud_client() as client:
            assert client._client.follow_redirects is True

    # do not follow redirects by default during unit tests
    async with get_cloud_client() as client:
        assert client._client.follow_redirects is False


async def test_get_cloud_work_pool_types():
    account_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    with temporary_settings(
        updates={
            PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/"
        }
    ):
        with respx.mock(
            assert_all_mocked=False, base_url=PREFECT_API_URL.value()
        ) as respx_mock:
            respx_mock.route(
                M(
                    host="api.prefect.cloud",
                    path__regex=(
                        r"api/accounts/(.{36})/workspaces/(.{36})/collections/work_pool_types"
                    ),
                ),
                method="GET",
            ).mock(
                return_value=httpx.Response(
                    200,
                    json=mock_work_pool_types_response,
                )
            )
            async with get_cloud_client() as client:
                response = await client.read_worker_metadata()
                assert response == mock_work_pool_types_response


async def test_read_current_workspace():
    account_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    api_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/"

    with temporary_settings(updates={PREFECT_API_URL: api_url}):
        with respx.mock(
            assert_all_mocked=False, base_url=PREFECT_API_URL.value()
        ) as respx_mock:
            respx_mock.get("https://api.prefect.cloud/api/me/workspaces").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "account_id": str(account_id),
                            "account_name": "Test Account",
                            "account_handle": "test-account",
                            "workspace_id": str(workspace_id),
                            "workspace_name": "Test Workspace",
                            "workspace_description": "Test workspace description",
                            "workspace_handle": "test-workspace",
                        }
                    ],
                )
            )

            async with get_cloud_client() as client:
                workspace = await client.read_current_workspace()
                assert workspace.workspace_id == workspace_id
                assert workspace.account_id == account_id
