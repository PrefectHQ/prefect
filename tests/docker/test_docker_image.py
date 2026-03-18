from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from prefect.docker.docker_image import DockerImage


class TestDockerImageStreamProgressTo:
    def test_stream_progress_to_default_is_none(self):
        image = DockerImage(name="test-image", tag="latest")
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
    def test_build_passes_none_when_no_stream(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_build_image: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(name="test-image", tag="latest")
        image.build()

        _, kwargs = mock_build_image.call_args
        assert kwargs["stream_progress_to"] is None

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

        image = DockerImage(name="test-image", tag="latest")
        image.push()  # should not raise
