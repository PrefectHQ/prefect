from prefect.client.cloud import get_cloud_client
from prefect.settings import PREFECT_UNIT_TEST_MODE, temporary_settings


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
