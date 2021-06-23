import logging
from unittest.mock import MagicMock

import docker
import pytest

from prefect.tasks.docker import (
    BuildImage,
    ListImages,
    PullImage,
    PushImage,
    RemoveImage,
    TagImage,
)


class DockerLoggingTestingUtilityMixin:
    @staticmethod
    def assert_logs_twice_on_success(task, caplog):
        with caplog.at_level(logging.DEBUG):
            task.run()
            # Reduce to relevant records
            records = [r for r in caplog.records if r.name == task.logger.name]

            assert len(records) == 2

            initial = records[0]
            final = records[1]

            assert any(image in initial.msg for image in ["image", "Image"])
            assert any(image in initial.msg for image in ["image", "Image"])

    @staticmethod
    def assert_logs_once_on_docker_api_failure(task, caplog):

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):
            with pytest.raises(docker.errors.DockerException):
                task.run()
                assert len(caplog.records) == 1
                assert any(image in caplog.text for image in ["image", "Image"])
                assert any(image not in caplog.text for image in ["image", "Image"])

    @staticmethod
    def assert_doesnt_log_on_param_failure(task, caplog):

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):
            with pytest.raises(ValueError):
                task.run()
                assert len(caplog.records) == 0


class TestListImagesTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = ListImages()
        assert not task.repository_name
        assert not task.all_layers
        assert not task.filters
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = ListImages(
            repository_name="test",
            all_layers=True,
            filters={"name": "test"},
            docker_server_url="test",
        )
        assert task.repository_name == "test"
        assert task.all_layers is True
        assert task.filters == {"name": "test"}
        assert task.docker_server_url == "test"

    def test_repository_name_init_value_is_used(self, monkeypatch):
        task = ListImages(repository_name="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.images.call_args[1]["name"] == "test"

    def test_repository_name_run_value_is_used(self, monkeypatch):
        task = ListImages()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository_name="test")
        assert api.return_value.images.call_args[1]["name"] == "test"

    def test_repository_name_is_replaced(self, monkeypatch):
        task = ListImages(repository_name="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository_name="test")
        assert api.return_value.images.call_args[1]["name"] == "test"

    def test_returns_list_images_value(self, monkeypatch, caplog):
        repo_name = "test repo"
        task = ListImages(repository_name=repo_name)

        api = MagicMock()
        expected_docker_output = ["A real image", "A second, equally real image"]

        api.return_value.images = MagicMock(return_value=expected_docker_output)
        monkeypatch.setattr("docker.APIClient", api)

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):

            result = task.run()
            assert result == expected_docker_output

            assert len(caplog.records) == 2

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        repo_name = "test repo"
        task = ListImages(repository_name=repo_name)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):
        repo_name = "test_repo"
        task = ListImages(repository_name=repo_name)

        api = MagicMock()
        images_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )
        api.return_value.images = images_mock

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)


class TestPullImageTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = PullImage()
        assert not task.repository
        assert not task.tag
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = PullImage(repository="test", tag="test", docker_server_url="test")
        assert task.repository == "test"
        assert task.tag == "test"
        assert task.docker_server_url == "test"

    def test_empty_repository_raises_error(self):
        task = PullImage()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_repository_raises_error(self):
        task = PullImage()
        with pytest.raises(ValueError):
            task.run(repository=None)

    def test_repository_init_value_is_used(self, monkeypatch):
        task = PullImage(repository="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.pull.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PullImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.pull.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PullImage(repository="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.pull.call_args[1]["repository"] == "test"

    def test_returns_pull_value(self, monkeypatch, caplog):

        task = PullImage(repository="original")

        api = MagicMock()
        expected_docker_output = "A real output from docker's api"

        api.return_value.pull = MagicMock(return_value=expected_docker_output)
        monkeypatch.setattr("docker.APIClient", api)

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):

            result = task.run(repository="test")
            assert result == expected_docker_output

    def test_returns_pull_value_with_stream_logs(self, monkeypatch, caplog):

        task = PullImage()

        api = MagicMock()
        expected_docker_output = [
            {"status": "Pulling"},
            {"status": "Digest"},
            {"status": "Test"},
        ]
        expected_result = (
            "{'status': 'Pulling'}\n{'status': 'Digest'}\n{'status': 'Test'}"
        )

        api.return_value.pull = MagicMock(return_value=expected_docker_output)
        monkeypatch.setattr("docker.APIClient", api)

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):

            result = task.run(repository="original", stream_logs=True)
            assert result == expected_result

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        tag = "A very specific tag for an image"
        repository = "An even more specific repository"
        task = PullImage(repository=repository, tag=tag)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = PullImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = PullImage(repository="test")

        api = MagicMock()
        pull_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )
        api.return_value.pull = pull_mock

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)


class TestPushImageTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = PushImage()
        assert not task.repository
        assert not task.tag
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = PushImage(repository="test", tag="test", docker_server_url="test")
        assert task.repository == "test"
        assert task.tag == "test"
        assert task.docker_server_url == "test"

    def test_empty_repository_raises_error(self):
        task = PushImage()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_repository_raises_error(self):
        task = PushImage()
        with pytest.raises(ValueError):
            task.run(repository=None)

    def test_repository_init_value_is_used(self, monkeypatch):
        task = PushImage(repository="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.push.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PushImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.push.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PushImage(repository="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.push.call_args[1]["repository"] == "test"

    def test_returns_push_value(self, monkeypatch, caplog):
        task = PushImage(repository="original")

        api = MagicMock()
        expected_docker_output = "An example push API response"

        api.return_value.push = MagicMock(return_value=expected_docker_output)
        monkeypatch.setattr("docker.APIClient", api)

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):

            result = task.run(repository="test")
            assert result == expected_docker_output

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        repository = "test repo"
        task = PushImage(repository=repository)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):
        repository = "test repo"
        task = PushImage(repository=repository)

        api = MagicMock()
        push_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )

        api.return_value.push = push_mock
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = PushImage()
        api = MagicMock()

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)


class TestRemoveImageTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = RemoveImage()
        assert not task.image
        assert not task.force
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = RemoveImage(image="test", force=True, docker_server_url="test")
        assert task.image == "test"
        assert task.force is True
        assert task.docker_server_url == "test"

    def test_empty_image_raises_error(self):
        task = RemoveImage()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_image_raises_error(self):
        task = RemoveImage()
        with pytest.raises(ValueError):
            task.run(image=None)

    def test_image_init_value_is_used(self, monkeypatch):
        task = RemoveImage(image="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.remove_image.call_args[1]["image"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = RemoveImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image="test")
        assert api.return_value.remove_image.call_args[1]["image"] == "test"

    def test_image_is_replaced(self, monkeypatch):
        task = RemoveImage(image="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image="test")
        assert api.return_value.remove_image.call_args[1]["image"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        image = "test image"
        task = RemoveImage(image=image)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = RemoveImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = RemoveImage(image="test")

        api = MagicMock()
        remove_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )
        api.return_value.remove_image = remove_mock
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)


class TestTagImageTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = TagImage()
        assert not task.image
        assert not task.repository
        assert not task.tag
        assert not task.force
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = TagImage(
            image="test",
            repository="test",
            tag="test",
            force=True,
            docker_server_url="test",
        )
        assert task.image == "test"
        assert task.repository == "test"
        assert task.tag == "test"
        assert task.force is True
        assert task.docker_server_url == "test"

    def test_empty_image_raises_error(self):
        task = TagImage()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_image_raises_error(self):
        task = TagImage()
        with pytest.raises(ValueError):
            task.run(image=None)

    def test_image_and_repository_init_value_is_used(self, monkeypatch):
        task = TagImage(image="test", repository="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_run_value_is_used(self, monkeypatch):
        task = TagImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image="test", repository="test")
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_is_replaced(self, monkeypatch):
        task = TagImage(image="original", repository="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(image="test", repository="test")
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"

    def test_returns_tag_value(self, monkeypatch, caplog):
        image = "an image thats going to get tagged"
        task = TagImage(image=image)
        expected_docker_output = image
        api = MagicMock()
        api.return_value.tag = MagicMock(return_value=expected_docker_output)
        monkeypatch.setattr("docker.APIClient", api)

        with caplog.at_level(logging.DEBUG, logger=task.logger.name):

            actual = task.run(image=image, repository="test")
            assert actual == expected_docker_output

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = TagImage(image="test", repository="test")

        api = MagicMock()
        tag_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )
        api.return_value.tag = tag_mock
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):

        task = TagImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        self.assert_doesnt_log_on_param_failure(task, caplog)

    def test_logs_twice_on_success(self, monkeypatch, caplog):

        task = TagImage(image="test", repository="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        tag = "test tag"
        image = "test image"
        repository = "test repo"

        self.assert_logs_twice_on_success(task, caplog)


class TestBuildImageTask(DockerLoggingTestingUtilityMixin):
    def test_empty_initialization(self):
        task = BuildImage()
        assert not task.path
        assert not task.tag
        assert not task.nocache
        assert task.rm
        assert not task.forcerm
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = BuildImage(
            path="test",
            tag="test",
            nocache=True,
            rm=False,
            forcerm=True,
            docker_server_url="test",
        )
        assert task.path == "test"
        assert task.tag == "test"
        assert task.nocache is True
        assert not task.rm
        assert task.forcerm is True
        assert task.docker_server_url == "test"

    def test_empty_path_raises_error(self):
        task = BuildImage()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_path_raises_error(self):
        task = BuildImage()
        with pytest.raises(ValueError):
            task.run(path=None)

    def test_path_init_value_is_used(self, monkeypatch):
        task = BuildImage(path="test")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run()
        assert api.return_value.build.call_args[1]["path"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = BuildImage()

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(path="test")
        assert api.return_value.build.call_args[1]["path"] == "test"

    def test_image_cleans_docker_output(self, monkeypatch):
        task = BuildImage()

        output = [
            b'{"stream":"Step 1/2 : FROM busybox"}\r\n{"stream":"\\n"}\r\n',
            b'{"stream":" ---\\u003e db8ee88ad75f\\n"}\r\n{"stream":"Step 2/2 : CMD [\\"echo\\", \\"foo\\"]"}\r\n{"stream":"\\n"}\r\n',
            b'{"stream":" ---\\u003e Using cache\\n"}\r\n{"stream":" ---\\u003e 0be8805a7d08\\n"}\r\n{"aux":{"ID":"sha256:0be8805a7d0828bbfcd876e8aa65cf6ee1ee016117a2d3f3aa4f21835ee1c69f"}}\r\n{"stream":"Successfully built 0be8805a7d08\\n"}\r\n',
        ]
        api = MagicMock()
        api.return_value.build.return_value = output
        monkeypatch.setattr("docker.APIClient", api)

        return_value = task.run(path="test")
        assert all(isinstance(value, dict) for value in return_value)
        assert all(len(value) >= 1 for value in return_value)
        assert all(key for value in return_value for key in value)

    def test_image_is_replaced(self, monkeypatch):
        task = BuildImage(path="original")

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)

        task.run(path="test")
        assert api.return_value.build.call_args[1]["path"] == "test"

    def test_logs_twice_on_success(self, monkeypatch, caplog):
        path = "test path"
        task = BuildImage(path=path)

        api = MagicMock()
        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_twice_on_success(task, caplog)

    def test_logs_once_on_docker_api_failure(self, monkeypatch, caplog):

        task = BuildImage(path="test")
        api = MagicMock()

        build_mock = MagicMock(
            side_effect=docker.errors.DockerException("Docker specific error")
        )

        api.return_value.build = build_mock

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_logs_once_on_docker_api_failure(task, caplog)

    def test_doesnt_log_on_param_failure(self, monkeypatch, caplog):
        task = BuildImage()
        api = MagicMock()

        monkeypatch.setattr("docker.APIClient", api)
        self.assert_doesnt_log_on_param_failure(task, caplog)
