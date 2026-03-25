from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from prefect.docker.docker_image import DockerImage


class TestDockerImageStreamProgressTo:
    def test_stream_progress_to_defaults_to_stdout(self):
        image = DockerImage(name="test-image", tag="latest")
        assert image.stream_progress_to is sys.stdout

    def test_stream_progress_to_can_be_set_to_none(self):
        image = DockerImage(name="test-image", tag="latest", stream_progress_to=None)
        assert image.stream_progress_to is None

    def test_stream_progress_to_is_stored(self):
        stream = io.StringIO()
        image = DockerImage(name="test-image", tag="latest", stream_progress_to=stream)
        assert image.stream_progress_to is stream

    @patch("prefect.docker.docker_image.build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_build_passes_stream_progress_to(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_build_image: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        stream = io.StringIO()
        image = DockerImage(name="test-image", tag="latest", stream_progress_to=stream)
        image.build()

        _, kwargs = mock_build_image.call_args
        assert kwargs["stream_progress_to"] is stream

    @patch("prefect.docker.docker_image.build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_build_passes_stdout_by_default(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_build_image: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(name="test-image", tag="latest")
        image.build()

        _, kwargs = mock_build_image.call_args
        assert kwargs["stream_progress_to"] is sys.stdout

    @patch("prefect.docker.docker_image.docker_client")
    def test_push_streams_progress(self, mock_docker_client: MagicMock):
        mock_client = MagicMock()
        mock_docker_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_docker_client.return_value.__exit__ = MagicMock()
        mock_client.api.push.return_value = [
            {"status": "Pushing", "progress": "[==>] 1MB/5MB"},
            {"status": "Pushed"},
        ]

        stream = io.StringIO()
        image = DockerImage(name="test-image", tag="latest", stream_progress_to=stream)
        image.push()

        output = stream.getvalue()
        assert "Pushing [==>] 1MB/5MB" in output
        assert "Pushed" in output

    @patch("prefect.docker.docker_image.docker_client")
    def test_push_without_stream_does_not_error(self, mock_docker_client: MagicMock):
        mock_client = MagicMock()
        mock_docker_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_docker_client.return_value.__exit__ = MagicMock()
        mock_client.api.push.return_value = [
            {"status": "Pushing"},
            {"status": "Pushed"},
        ]

        image = DockerImage(name="test-image", tag="latest", stream_progress_to=None)
        image.push()  # should not raise


class TestDockerImageBuildBackend:
    def test_default_build_backend_is_docker_py(self):
        image = DockerImage(name="test-image", tag="latest")
        assert image.build_backend == "docker-py"

    def test_buildx_backend_is_stored(self):
        image = DockerImage(name="test-image", tag="latest", build_backend="buildx")
        assert image.build_backend == "buildx"

    def test_invalid_build_backend_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid build_backend"):
            DockerImage(name="test-image", tag="latest", build_backend="invalid")

    @patch("prefect.docker.docker_image.build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_docker_py_backend_calls_build_image(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_build_image: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(name="test-image", tag="latest", build_backend="docker-py")
        image.build()

        mock_build_image.assert_called_once()

    @patch("prefect.docker._buildx.buildx_build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_buildx_backend_calls_buildx_build_image(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_buildx_build: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(name="test-image", tag="latest", build_backend="buildx")
        image.build()

        mock_buildx_build.assert_called_once()

    @patch("prefect.docker._buildx.buildx_build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_buildx_build_kwargs_forwarded(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_buildx_build: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(
            name="test-image",
            tag="latest",
            build_backend="buildx",
            secrets=["id=mysecret,src=secret.txt"],
            cache_from=["type=registry,ref=myimage:cache"],
        )
        image.build()

        call_kwargs = mock_buildx_build.call_args[1]
        assert call_kwargs["secrets"] == ["id=mysecret,src=secret.txt"]
        assert call_kwargs["cache_from"] == ["type=registry,ref=myimage:cache"]

    @patch("prefect.docker._buildx.buildx_build_image")
    def test_buildx_build_with_push(self, mock_buildx_build: MagicMock):
        image = DockerImage(
            name="test-image",
            tag="latest",
            build_backend="buildx",
            dockerfile="Dockerfile",
            push=True,
        )
        image.build()

        call_kwargs = mock_buildx_build.call_args[1]
        assert call_kwargs.get("push") is True  # push passed through as positional
        assert image._pushed_during_build is True

    @patch("prefect.docker._buildx.buildx_push_image")
    @patch("prefect.docker._buildx.buildx_build_image")
    def test_buildx_push_is_noop_after_push_build(
        self,
        mock_buildx_build: MagicMock,
        mock_buildx_push: MagicMock,
    ):
        image = DockerImage(
            name="test-image",
            tag="latest",
            build_backend="buildx",
            dockerfile="Dockerfile",
            push=True,
        )
        image.build()
        image.push()

        mock_buildx_push.assert_not_called()

    @patch("prefect.docker._buildx.buildx_push_image")
    @patch("prefect.docker._buildx.buildx_build_image")
    def test_buildx_push_calls_buildx_push_image(
        self,
        mock_buildx_build: MagicMock,
        mock_buildx_push: MagicMock,
    ):
        image = DockerImage(
            name="test-image",
            tag="latest",
            build_backend="buildx",
            dockerfile="Dockerfile",
        )
        image.build()
        image.push()

        mock_buildx_push.assert_called_once_with(
            name="test-image",
            tag="latest",
            stream_progress_to=image.stream_progress_to,
        )

    @patch("prefect.docker.docker_image.docker_client")
    def test_docker_py_push_still_works(self, mock_docker_client: MagicMock):
        mock_client = MagicMock()
        mock_docker_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_docker_client.return_value.__exit__ = MagicMock()
        mock_client.api.push.return_value = [{"status": "Pushed"}]

        image = DockerImage(name="test-image", tag="latest", build_backend="docker-py")
        image.push()

        mock_client.api.push.assert_called_once()
