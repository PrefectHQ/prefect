from unittest.mock import MagicMock

import pytest

from prefect.tasks.docker import (
    BuildImage,
    ListImages,
    PullImage,
    PushImage,
    RemoveImage,
    TagImage,
)


class TestListImagesTask:
    def test_empty_initialization(self):
        task = ListImages()
        assert not task.repository_name
        assert not task.all_layers
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = ListImages(
            repository_name="test", all_layers=True, docker_server_url="test"
        )
        assert task.repository_name == "test"
        assert task.all_layers == True
        assert task.docker_server_url == "test"

    def test_repository_name_init_value_is_used(self, monkeypatch):
        task = ListImages(repository_name="test")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.images.call_args[1]["name"] == "test"

    def test_repository_name_run_value_is_used(self, monkeypatch):
        task = ListImages()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository_name="test")
        assert api.return_value.images.call_args[1]["name"] == "test"

    def test_repository_name_is_replaced(self, monkeypatch):
        task = ListImages(repository_name="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository_name="test")
        assert api.return_value.images.call_args[1]["name"] == "test"


class TestPullImageTask:
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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.pull.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PullImage()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.pull.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PullImage(repository="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.pull.call_args[1]["repository"] == "test"


class TestPushImageTask:
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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.push.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PushImage()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.push.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PushImage(repository="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(repository="test")
        assert api.return_value.push.call_args[1]["repository"] == "test"


class TestRemoveImageTask:
    def test_empty_initialization(self):
        task = RemoveImage()
        assert not task.image
        assert not task.force
        assert task.docker_server_url == "unix:///var/run/docker.sock"

    def test_filled_initialization(self):
        task = RemoveImage(image="test", force=True, docker_server_url="test")
        assert task.image == "test"
        assert task.force == True
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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.remove_image.call_args[1]["image"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = RemoveImage()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image="test")
        assert api.return_value.remove_image.call_args[1]["image"] == "test"

    def test_image_is_replaced(self, monkeypatch):
        task = RemoveImage(image="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image="test")
        assert api.return_value.remove_image.call_args[1]["image"] == "test"


class TestTagImageTask:
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
        assert task.force == True
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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_run_value_is_used(self, monkeypatch):
        task = TagImage()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image="test", repository="test")
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_is_replaced(self, monkeypatch):
        task = TagImage(image="original", repository="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(image="test", repository="test")
        assert api.return_value.tag.call_args[1]["image"] == "test"
        assert api.return_value.tag.call_args[1]["repository"] == "test"


class TestBuildImageTask:
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
        assert task.nocache == True
        assert not task.rm
        assert task.forcerm == True
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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run()
        assert api.return_value.build.call_args[1]["path"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = BuildImage()

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

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
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        return_value = task.run(path="test")
        assert all([isinstance(value, dict) for value in return_value])
        assert all([len(value) >= 1 for value in return_value])
        assert all([key for value in return_value for key in value])

    def test_image_is_replaced(self, monkeypatch):
        task = BuildImage(path="original")

        api = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.containers.docker.APIClient", api)

        task.run(path="test")
        assert api.return_value.build.call_args[1]["path"] == "test"
