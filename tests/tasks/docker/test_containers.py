from unittest.mock import MagicMock

import pytest

from prefect.engine.signals import FAIL
from prefect.tasks.docker import (
    CreateContainer,
    GetContainerLogs,
    ListContainers,
    StartContainer,
    StopContainer,
    WaitOnContainer,
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

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.create_container.call_args[1]["image"] == "test"

    def test_image_name_run_value_is_used(self, monkeypatch):
        task = CreateContainer()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image_name="test")
        assert api.return_value.create_container.call_args[1]["image"] == "test"

    def test_image_name_is_replaced(self, monkeypatch):
        task = CreateContainer(image_name="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image_name="test")
        assert api.return_value.create_container.call_args[1]["image"] == "test"


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

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.logs.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = GetContainerLogs()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.logs.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = GetContainerLogs(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.logs.call_args[1]["container"] == "test"


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

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.containers.call_args[1]["all"]

    def test_all_containers_run_value_is_used(self, monkeypatch):
        task = ListContainers()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(all_containers=True)
        assert api.return_value.containers.call_args[1]["all"]

    def test_all_containers_is_replaced(self, monkeypatch):
        task = ListContainers(all_containers=False)

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(all_containers=True)
        assert api.return_value.containers.call_args[1]["all"]


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

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.start.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StartContainer()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.start.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StartContainer(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.start.call_args[1]["container"] == "test"


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

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.stop.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StopContainer()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.stop.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StopContainer(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.stop.call_args[1]["container"] == "test"


class TestWaitOnContainerTask:
    def test_empty_initialization(self):
        task = WaitOnContainer()
        assert not task.container_id
        assert task.docker_server_url == "unix:///var/run/docker.sock"
        assert task.raise_on_exit_code is True

    def test_filled_initialization(self):
        task = WaitOnContainer(
            container_id="test", docker_server_url="test", raise_on_exit_code=False
        )
        assert task.container_id == "test"
        assert task.docker_server_url == "test"
        assert task.raise_on_exit_code is False

    def test_empty_container_id_raises_error(self):
        task = WaitOnContainer()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_container_id_raises_error(self):
        task = WaitOnContainer()
        with pytest.raises(ValueError):
            task.run(container_id=None)

    def test_container_id_init_value_is_used(self, monkeypatch):
        task = WaitOnContainer(container_id="test")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)
        api.return_value.wait.return_value = {}

        task.run()
        assert api.return_value.wait.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = WaitOnContainer(container_id="init")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)
        api.return_value.wait.return_value = {}

        task.run(container_id="test")
        assert api.return_value.wait.call_args[1]["container"] == "test"

    def test_raises_for_nonzero_status(self, monkeypatch):
        task = WaitOnContainer(container_id="noise")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)
        api.return_value.wait.return_value = {"StatusCode": 1}

        with pytest.raises(FAIL):
            task.run()

    def test_raises_for_error(self, monkeypatch):
        task = WaitOnContainer(container_id="noise")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)
        api.return_value.wait.return_value = {"Error": "oops!"}

        with pytest.raises(FAIL):
            task.run()

    def test_doesnt_raise_for_nonzero_status(self, monkeypatch):
        task = WaitOnContainer(container_id="noise", raise_on_exit_code=False)

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)
        api.return_value.wait.return_value = {"StatusCode": 1, "Error": "oops!"}

        task.run()
