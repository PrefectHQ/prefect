from unittest.mock import MagicMock

from prefect_docker.containers import (
    create_docker_container,
    get_docker_container_logs,
    remove_docker_container,
    start_docker_container,
    stop_docker_container,
)

from prefect.logging import disable_run_logger


class TestCreateDockerContainer:
    async def test_create_kwargs(self, mock_docker_host: MagicMock):
        create_kwargs = dict(
            image="test_image",
            command="test_command",
            name="test_name",
            detach=False,
            ports={"2222/tcp": 3333},
            entrypoint=None,
            environment=None,
        )
        with disable_run_logger():
            container = await create_docker_container.fn(
                docker_host=mock_docker_host, **create_kwargs
            )
        assert container.id == "id_1"

        client = mock_docker_host.get_client()
        client.__enter__.return_value.containers.create.assert_called_once_with(
            **create_kwargs
        )


class TestGetDockerContainerLogs:
    async def test_logs_kwargs(self, mock_docker_host: MagicMock):
        logs_kwargs = dict(container_id="42")
        with disable_run_logger():
            logs = await get_docker_container_logs.fn(
                docker_host=mock_docker_host, **logs_kwargs
            )
        assert logs == "here are logs"

        client = mock_docker_host.get_client()
        client.__enter__.return_value.containers.get.assert_called_once_with("42")


class TestStartDockerContainer:
    async def test_start_kwargs(self, mock_docker_host: MagicMock):
        start_kwargs = dict(container_id="42")
        with disable_run_logger():
            container = await start_docker_container.fn(
                docker_host=mock_docker_host, **start_kwargs
            )
        assert container.id == "42"

        client = mock_docker_host.get_client()
        client.__enter__.return_value.containers.get.assert_called_once_with("42")


class TestStopDockerContainer:
    async def test_stop_kwargs(self, mock_docker_host: MagicMock):
        stop_kwargs = dict(container_id="42")
        with disable_run_logger():
            container = await stop_docker_container.fn(
                docker_host=mock_docker_host, **stop_kwargs
            )
        assert container.id == "42"

        client = mock_docker_host.get_client()
        client.__enter__.return_value.containers.get.assert_called_once_with("42")


class TestRemoveDockerContainer:
    async def test_remove_kwargs(self, mock_docker_host: MagicMock):
        remove_kwargs = dict(container_id="42")
        with disable_run_logger():
            container = await remove_docker_container.fn(
                docker_host=mock_docker_host, **remove_kwargs
            )
        assert container.id == "42"

        client = mock_docker_host.get_client()
        client.__enter__.return_value.containers.get.assert_called_once_with("42")
