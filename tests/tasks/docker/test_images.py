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

        images = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.images", images
        )

        task.run()
        assert images.call_args[1]["name"] == "test"

    def test_repository_name_run_value_is_used(self, monkeypatch):
        task = ListImages()

        images = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.images", images
        )

        task.run(repository_name="test")
        assert images.call_args[1]["name"] == "test"

    def test_repository_name_is_replaced(self, monkeypatch):
        task = ListImages(repository_name="original")

        images = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.images", images
        )

        task.run(repository_name="test")
        assert images.call_args[1]["name"] == "test"


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

        pull = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.pull", pull)

        task.run()
        assert pull.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PullImage()

        pull = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.pull", pull)

        task.run(repository="test")
        assert pull.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PullImage(repository="original")

        pull = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.pull", pull)

        task.run(repository="test")
        assert pull.call_args[1]["repository"] == "test"


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

        push = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.push", push)

        task.run()
        assert push.call_args[1]["repository"] == "test"

    def test_repository_run_value_is_used(self, monkeypatch):
        task = PushImage()

        push = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.push", push)

        task.run(repository="test")
        assert push.call_args[1]["repository"] == "test"

    def test_repository_is_replaced(self, monkeypatch):
        task = PushImage(repository="original")

        push = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.push", push)

        task.run(repository="test")
        assert push.call_args[1]["repository"] == "test"


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

        remove = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.remove_image", remove
        )

        task.run()
        assert remove.call_args[1]["image"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = RemoveImage()

        remove = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.remove_image", remove
        )

        task.run(image="test")
        assert remove.call_args[1]["image"] == "test"

    def test_image_is_replaced(self, monkeypatch):
        task = RemoveImage(image="original")

        remove = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.docker.images.docker.APIClient.remove_image", remove
        )

        task.run(image="test")
        assert remove.call_args[1]["image"] == "test"


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

        tag = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.tag", tag)

        task.run()
        assert tag.call_args[1]["image"] == "test"
        assert tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_run_value_is_used(self, monkeypatch):
        task = TagImage()

        tag = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.tag", tag)

        task.run(image="test", repository="test")
        assert tag.call_args[1]["image"] == "test"
        assert tag.call_args[1]["repository"] == "test"

    def test_image_and_repository_is_replaced(self, monkeypatch):
        task = TagImage(image="original", repository="original")

        tag = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.tag", tag)

        task.run(image="test", repository="test")
        assert tag.call_args[1]["image"] == "test"
        assert tag.call_args[1]["repository"] == "test"


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

        build = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.build", build)

        task.run()
        assert build.call_args[1]["path"] == "test"

    def test_image_run_value_is_used(self, monkeypatch):
        task = BuildImage()

        build = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.build", build)

        task.run(path="test")
        assert build.call_args[1]["path"] == "test"

    def test_image_is_replaced(self, monkeypatch):
        task = BuildImage(path="original")

        build = MagicMock()
        monkeypatch.setattr("prefect.tasks.docker.images.docker.APIClient.build", build)

        task.run(path="test")
        assert build.call_args[1]["path"] == "test"
