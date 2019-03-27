from unittest.mock import MagicMock

import pytest

from prefect.tasks.docker import (
    CreateContainer,
    GetContainerLogs,
    ListContainers,
    StartContainer,
    StopContainer,
)


class TestCreateContainerTask:
    def test_empty_initialization(self):
        task = CreateContainer()
        assert not task.image_name
        assert not task.command
        assert not task.detach
        assert not task.entrypoint
        assert not task.environment
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = CreateContainer(
            image_name="test",
            command="test",
            detach=True,
            entrypoint=["test"],
            environment=["test"],
            name="test",
            docker_server_url="test",
        )
        assert task.image_name == "test"
        assert task.command == "test"
        assert task.detach
        assert task.entrypoint == ["test"]
        assert task.environment == ["test"]
        assert task.docker_server_url == "test"

    def test_empty_image_name_raises_error(self):
        task = CreateContainer()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_image_name_raises_error(self):
        task = CreateContainer()
        with pytest.raises(ValueError):
            task.run(image_name=None)

    def test_image_name_init_value_is_used(self, monkeypatch):
        task = CreateContainer(image_name="test")

        create_container = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.create_container",
            create_container,
        )

        task.run()
        assert create_container.call_args[1]["image"] == "test"

    def test_image_name_run_value_is_used(self, monkeypatch):
        task = CreateContainer()

        create_container = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.create_container",
            create_container,
        )

        task.run(image_name="test")
        assert create_container.call_args[1]["image"] == "test"

    def test_image_name_is_replaced(self, monkeypatch):
        task = CreateContainer(image_name="original")

        create_container = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.create_container",
            create_container,
        )

        task.run(image_name="test")
        assert create_container.call_args[1]["image"] == "test"


class TestGetContainerLogsTask:
    def test_empty_initialization(self):
        task = GetContainerLogs()
        assert not task.container_id
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = GetContainerLogs(container_id="test", docker_server_url="test")
        assert task.container_id == "test"
        assert task.docker_server_url == "test"

    def test_empty_container_id_raises_error(self):
        task = GetContainerLogs()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_container_id_raises_error(self):
        task = GetContainerLogs()
        with pytest.raises(ValueError):
            task.run(container_id=None)

    def test_container_id_init_value_is_used(self, monkeypatch):
        task = GetContainerLogs(container_id="test")

        logs = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.logs", logs
        )

        task.run()
        assert logs.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = GetContainerLogs()

        logs = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.logs", logs
        )

        task.run(container_id="test")
        assert logs.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = GetContainerLogs(container_id="original")

        logs = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.logs", logs
        )

        task.run(container_id="test")
        assert logs.call_args[1]["container"] == "test"


class TestListContainersTask:
    def test_empty_initialization(self):
        task = ListContainers()
        assert not task.all_containers
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = ListContainers(all_containers=True, docker_server_url="test")
        assert task.all_containers == True
        assert task.docker_server_url == "test"

    def test_all_containers_init_value_is_used(self, monkeypatch):
        task = ListContainers(all_containers=True)

        containers = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.containers", containers
        )

        task.run()
        assert containers.call_args[1]["all"]

    def test_all_containers_run_value_is_used(self, monkeypatch):
        task = ListContainers()

        containers = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.containers", containers
        )

        task.run(all_containers=True)
        assert containers.call_args[1]["all"]

    def test_all_containers_is_replaced(self, monkeypatch):
        task = ListContainers(all_containers=False)

        containers = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.containers", containers
        )

        task.run(all_containers=True)
        assert containers.call_args[1]["all"]


class TestStartContainerTask:
    def test_empty_initialization(self):
        task = StartContainer()
        assert not task.container_id
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = StartContainer(container_id="test", docker_server_url="test")
        assert task.container_id == "test"
        assert task.docker_server_url == "test"

    def test_empty_container_id_raises_error(self):
        task = StartContainer()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_container_id_raises_error(self):
        task = StartContainer()
        with pytest.raises(ValueError):
            task.run(container_id=None)

    def test_container_id_init_value_is_used(self, monkeypatch):
        task = StartContainer(container_id="test")

        start = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.start", start
        )

        task.run()
        assert start.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StartContainer()

        start = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.start", start
        )

        task.run(container_id="test")
        assert start.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StartContainer(container_id="original")

        start = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.start", start
        )

        task.run(container_id="test")
        assert start.call_args[1]["container"] == "test"


class TestStopContainerTask:
    def test_empty_initialization(self):
        task = StopContainer()
        assert not task.container_id
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = StopContainer(container_id="test", docker_server_url="test")
        assert task.container_id == "test"
        assert task.docker_server_url == "test"

    def test_empty_container_id_raises_error(self):
        task = StopContainer()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_container_id_raises_error(self):
        task = StopContainer()
        with pytest.raises(ValueError):
            task.run(container_id=None)

    def test_container_id_init_value_is_used(self, monkeypatch):
        task = StopContainer(container_id="test")

        stop = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.stop", stop
        )

        task.run()
        assert stop.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StopContainer()

        stop = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.stop", stop
        )

        task.run(container_id="test")
        assert stop.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StopContainer(container_id="original")

        stop = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.containers.docker.APIClient.stop", stop
        )

        task.run(container_id="test")
        assert stop.call_args[1]["container"] == "test"
