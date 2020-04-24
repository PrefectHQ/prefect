import logging
from unittest.mock import MagicMock

import docker
import pytest

from prefect.engine.signals import FAIL
from prefect.tasks.docker import (
    CreateContainer,
    GetContainerLogs,
    ListContainers,
    StartContainer,
    StopContainer,
    RemoveContainer,
    WaitOnContainer,
)


class DockerLoggingTestingUtilityMixin:
    @staticmethod
    def assert_logs_twice_on_success(task, caplog):

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):
            task.run()
            assert len(caplog.records) == 2

            initial = caplog.records[0]
            final = caplog.records[1]

            assert "Starting" in initial.msg
            assert "Completed" in final.msg

    @staticmethod
    def assert_logs_once_on_docker_api_failure(task, caplog):

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):
            with pytest.raises(docker.errors.DockerException):
                task.run()
                assert len(caplog.records) == 1
                assert "Starting" in caplog.text
                assert "Completed" not in caplog.text

    @staticmethod
    def assert_doesnt_log_on_param_failure(task, caplog):

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):
            with pytest.raises(ValueError):
                task.run()
                assert len(caplog.records) == 0


class TestCreateContainerTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = CreateContainer()
        assert not task.image_name
        assert not task.command
        assert not task.detach
        assert not task.entrypoint
        assert not task.environment
        assert not task.volumes
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = CreateContainer(
            image_name="test",
            command="test",
            detach=True,
            entrypoint=["test"],
            environment=["test"],
            volumes=["/tmp/test:/tmp/test:ro"],
            name="test",
            docker_server_url="test",
        )
        assert task.image_name == "test"
        assert task.command == "test"
        assert task.detach
        assert task.entrypoint == ["test"]
        assert task.environment == ["test"]
        assert task.volumes == ["/tmp/test:/tmp/test:ro"]
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
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.create_container.call_args[1]["image"] == "test"

    def test_image_name_run_value_is_used(self, monkeypatch):
        task = CreateContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image_name="test")
        assert api.return_value.create_container.call_args[1]["image"] == "test"

    def test_image_name_is_replaced(self, monkeypatch):
        task = CreateContainer(image_name="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image_name="test")
        assert api.return_value.create_container.call_args[1]["image"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        image_name = "test image"
        task = CreateContainer(image_name=image_name)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        image_name = "test image"
        task = CreateContainer(image_name=image_name)

        api = MagicMock()
        create_container_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.create_container = create_container_mock
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):
        image_name = "test image"
        task = CreateContainer()

        api = MagicMock()

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestGetContainerLogsTask(DockerLoggingTestingUtilityMixin):
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
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.logs.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = GetContainerLogs()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.logs.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = GetContainerLogs(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.logs.call_args[1]["container"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = GetContainerLogs(container_id="test")
        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):
        task = GetContainerLogs(container_id="test")
        api = MagicMock()
        get_container_logs_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.logs = get_container_logs_mock

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = GetContainerLogs()
        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestListContainersTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = ListContainers()
        assert not task.all_containers
        assert not task.filters
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = ListContainers(
            all_containers=True, filters={"name": "test"}, docker_server_url="test"
        )
        assert task.all_containers == True
        assert task.filters == {"name": "test"}
        assert task.docker_server_url == "test"

    def test_all_containers_init_value_is_used(self, monkeypatch):
        task = ListContainers(all_containers=True)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.containers.call_args[1]["all"]

    def test_all_containers_run_value_is_used(self, monkeypatch):
        task = ListContainers()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(all_containers=True)
        assert api.return_value.containers.call_args[1]["all"]

    def test_all_containers_is_replaced(self, monkeypatch):
        task = ListContainers(all_containers=False)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(all_containers=True)
        assert api.return_value.containers.call_args[1]["all"]

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = ListContainers(all_containers=False)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):
        task = ListContainers(all_containers=False)

        api = MagicMock()
        list_containers_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.containers = list_containers_mock
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)


class TestStartContainerTask(DockerLoggingTestingUtilityMixin):
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
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.start.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StartContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.start.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StartContainer(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.start.call_args[1]["container"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        task = StartContainer(container_id="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = StartContainer(container_id="test")

        api = MagicMock()
        start_container_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.start = start_container_mock
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = StartContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestStopContainerTask(DockerLoggingTestingUtilityMixin):
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
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.stop.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = StopContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.stop.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = StopContainer(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.stop.call_args[1]["container"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = StopContainer(container_id="test")
        api = MagicMock()

        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = StopContainer(container_id="original")

        api = MagicMock()
        stop_container_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.stop = stop_container_mock
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = StopContainer()
        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestRemoveContainerTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = RemoveContainer()
        assert not task.container_id
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = RemoveContainer(container_id="test", docker_server_url="test")
        assert task.container_id == "test"
        assert task.docker_server_url == "test"

    def test_empty_container_id_raises_error(self):
        task = RemoveContainer()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_container_id_raises_error(self):
        task = RemoveContainer()
        with pytest.raises(ValueError):
            task.run(container_id=None)

    def test_container_id_init_value_is_used(self, monkeypatch):
        task = RemoveContainer(container_id="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.remove_container.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = RemoveContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.remove_container.call_args[1]["container"] == "test"

    def test_container_id_is_replaced(self, monkeypatch):
        task = RemoveContainer(container_id="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(container_id="test")
        assert api.return_value.remove_container.call_args[1]["container"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = RemoveContainer(container_id="test")
        api = MagicMock()

        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = RemoveContainer(container_id="original")

        api = MagicMock()
        remove_container_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.remove_container = remove_container_mock
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = RemoveContainer()
        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestWaitOnContainerTask(DockerLoggingTestingUtilityMixin):
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
        monkeypatch.setattr("docker.APIClient", api)
        api.return_value.wait.return_value = {}

        task.run()
        assert api.return_value.wait.call_args[1]["container"] == "test"

    def test_container_id_run_value_is_used(self, monkeypatch):
        task = WaitOnContainer(container_id="init")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        api.return_value.wait.return_value = {}

        task.run(container_id="test")
        assert api.return_value.wait.call_args[1]["container"] == "test"

    def test_raises_for_nonzero_status(self, monkeypatch):
        task = WaitOnContainer(container_id="noise")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        api.return_value.wait.return_value = {"StatusCode": 1}

        with pytest.raises(FAIL):
            task.run()

    def test_raises_for_error(self, monkeypatch):
        task = WaitOnContainer(container_id="noise")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        api.return_value.wait.return_value = {"Error": "oops!"}

        with pytest.raises(FAIL):
            task.run()

    def test_doesnt_raise_for_nonzero_status(self, monkeypatch):
        task = WaitOnContainer(container_id="noise", raise_on_exit_code=False)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        api.return_value.wait.return_value = {"StatusCode": 1, "Error": "oops!"}

        task.run()

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = WaitOnContainer(container_id="noise", raise_on_exit_code=False)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = WaitOnContainer(container_id="noise")

        api = MagicMock()
        wait_container_mock = MagicMock(
            side_effect=docker.errors.DockerException("A docker specific exception")
        )
        api.return_value.wait = wait_container_mock
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = WaitOnContainer()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)
