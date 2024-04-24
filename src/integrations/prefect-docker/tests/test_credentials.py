from unittest.mock import MagicMock

from prefect.logging import disable_run_logger


async def test_docker_registry_credentials_login(
    mock_docker_host: MagicMock, mock_docker_registry_credentials: MagicMock
):
    client = mock_docker_host.get_client()
    with disable_run_logger():
        await mock_docker_registry_credentials.login(client=client)
    assert client._authenticated
