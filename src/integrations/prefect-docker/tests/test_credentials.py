from unittest.mock import MagicMock

from prefect_docker import DockerRegistryCredentials

from prefect.logging import disable_run_logger


async def test_docker_registry_credentials_login(
    mock_docker_host: MagicMock, mock_docker_registry_credentials: MagicMock
):
    client = mock_docker_host.get_client()
    with disable_run_logger():
        await mock_docker_registry_credentials.login(client=client)
    assert client._authenticated


async def test_docker_registry_credentials_login_works_outside_flow_run_context(
    mock_docker_client: MagicMock,
):
    """Test that login works without an active flow run context."""
    credentials = DockerRegistryCredentials(
        username="test_user",
        password="test_password",
        registry_url="registry.hub.docker.com",
    )
    # This should not raise MissingContextError
    await credentials.login(client=mock_docker_client)
    mock_docker_client.login.assert_called_once_with(
        username="test_user",
        password="test_password",
        registry="registry.hub.docker.com",
        reauth=True,
    )
