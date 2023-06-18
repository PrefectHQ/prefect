from prefect.client.cloud import get_cloud_client


async def test_cloud_client_follow_redirects():
    async with get_cloud_client() as client:
        assert client._client.follow_redirects is True

    httpx_settings = {"follow_redirects": True}
    async with get_cloud_client(httpx_settings=httpx_settings) as client:
        assert client._client.follow_redirects is True

    httpx_settings = {"follow_redirects": False}
    async with get_cloud_client(httpx_settings=httpx_settings) as client:
        assert client._client.follow_redirects is False
