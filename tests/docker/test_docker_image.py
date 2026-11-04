from __future__ import annotations

import io
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal
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

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    def test_buildx_backend_is_stored(self, _mock_guard: MagicMock):
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

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    @patch("prefect._internal.buildx.buildx_build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_buildx_backend_calls_buildx_build_image(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_buildx_build: MagicMock,
        _mock_guard: MagicMock,
    ):
        mock_generate_dockerfile.return_value.__enter__ = MagicMock()
        mock_generate_dockerfile.return_value.__exit__ = MagicMock()

        image = DockerImage(name="test-image", tag="latest", build_backend="buildx")
        image.build()

        mock_buildx_build.assert_called_once()

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    @patch("prefect._internal.buildx.buildx_build_image")
    @patch("prefect.docker.docker_image.generate_default_dockerfile")
    def test_buildx_build_kwargs_forwarded(
        self,
        mock_generate_dockerfile: MagicMock,
        mock_buildx_build: MagicMock,
        _mock_guard: MagicMock,
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

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    @patch("prefect._internal.buildx.buildx_build_image")
    def test_buildx_build_with_push(
        self, mock_buildx_build: MagicMock, _mock_guard: MagicMock
    ):
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

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    @patch("prefect._internal.buildx.buildx_push_image")
    @patch("prefect._internal.buildx.buildx_build_image")
    def test_buildx_push_is_noop_after_push_build(
        self,
        mock_buildx_build: MagicMock,
        mock_buildx_push: MagicMock,
        _mock_guard: MagicMock,
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

    @patch("prefect.docker.docker_image._ensure_buildx_extra")
    @patch("prefect._internal.buildx.buildx_push_image")
    @patch("prefect._internal.buildx.buildx_build_image")
    def test_buildx_push_calls_buildx_push_image(
        self,
        mock_buildx_build: MagicMock,
        mock_buildx_push: MagicMock,
        _mock_guard: MagicMock,
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


class TestDockerImageAutoDockerfileContext:
    @pytest.fixture
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.chdir(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        (project / "requirements.txt").write_text("httpx\n")
        return project

    @pytest.fixture
    def mock_build_image(self) -> Generator[MagicMock, None, None]:
        with patch("prefect.docker.docker_image.build_image") as mock:
            yield mock

    @pytest.fixture
    def mock_buildx_build_image(self) -> Generator[MagicMock, None, None]:
        with (
            patch("prefect.docker.docker_image._ensure_buildx_extra"),
            patch("prefect._internal.buildx.buildx_build_image") as mock,
        ):
            yield mock

    @staticmethod
    def _capture_dockerfile(mock: MagicMock) -> dict[str, Any]:
        captured: dict[str, Any] = {}

        def inspect_build(**kwargs: Any) -> None:
            dockerfile = Path(kwargs["context"]) / "Dockerfile"
            captured["context"] = kwargs["context"]
            captured["dockerfile"] = (
                dockerfile.read_text() if dockerfile.exists() else None
            )
            captured["cwd_dockerfile_exists"] = (Path.cwd() / "Dockerfile").exists()

        mock.side_effect = inspect_build
        return captured

    @pytest.mark.parametrize("as_str", [False, True])
    def test_docker_py_generates_dockerfile_in_context(
        self, project: Path, mock_build_image: MagicMock, as_str: bool
    ):
        captured = self._capture_dockerfile(mock_build_image)
        context = str(project) if as_str else project

        DockerImage(name="test-image", tag="latest", context=context).build()

        assert captured["context"] == context
        assert captured["dockerfile"] is not None
        assert (
            "COPY requirements.txt /opt/prefect/project/requirements.txt"
            in (captured["dockerfile"])
        )
        assert "WORKDIR /opt/prefect/project/" in captured["dockerfile"]
        assert not captured["cwd_dockerfile_exists"]
        assert not (project / "Dockerfile").exists()

    @pytest.mark.parametrize("as_str", [False, True])
    def test_buildx_generates_dockerfile_in_context(
        self, project: Path, mock_buildx_build_image: MagicMock, as_str: bool
    ):
        captured = self._capture_dockerfile(mock_buildx_build_image)
        context = str(project) if as_str else project

        DockerImage(
            name="test-image", tag="latest", build_backend="buildx", context=context
        ).build()

        assert captured["context"] == context
        assert captured["dockerfile"] is not None
        assert (
            "COPY requirements.txt /opt/prefect/project/requirements.txt"
            in (captured["dockerfile"])
        )
        assert "WORKDIR /opt/prefect/project/" in captured["dockerfile"]
        assert not captured["cwd_dockerfile_exists"]
        assert not (project / "Dockerfile").exists()

    @pytest.mark.parametrize("build_backend", ["docker-py", "buildx"])
    def test_existing_dockerfile_in_cwd_does_not_block_context_build(
        self,
        project: Path,
        mock_build_image: MagicMock,
        mock_buildx_build_image: MagicMock,
        build_backend: Literal["docker-py", "buildx"],
    ):
        cwd_dockerfile = Path.cwd() / "Dockerfile"
        cwd_dockerfile.write_text("FROM scratch\n")

        DockerImage(
            name="test-image",
            tag="latest",
            build_backend=build_backend,
            context=project,
        ).build()

        assert cwd_dockerfile.read_text() == "FROM scratch\n"
        assert not (project / "Dockerfile").exists()

    @pytest.mark.parametrize("build_backend", ["docker-py", "buildx"])
    def test_generated_dockerfile_removed_when_build_fails(
        self,
        project: Path,
        mock_build_image: MagicMock,
        mock_buildx_build_image: MagicMock,
        build_backend: Literal["docker-py", "buildx"],
    ):
        mock_build_image.side_effect = RuntimeError("boom")
        mock_buildx_build_image.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            DockerImage(
                name="test-image",
                tag="latest",
                build_backend=build_backend,
                context=project,
            ).build()

        assert not (project / "Dockerfile").exists()

    @pytest.mark.parametrize("build_backend", ["docker-py", "buildx"])
    def test_defaults_to_cwd_without_context(
        self,
        project: Path,
        mock_build_image: MagicMock,
        mock_buildx_build_image: MagicMock,
        build_backend: Literal["docker-py", "buildx"],
    ):
        mock = (
            mock_build_image
            if build_backend == "docker-py"
            else mock_buildx_build_image
        )
        captured = self._capture_dockerfile(mock)
        cwd = Path.cwd()

        DockerImage(
            name="test-image", tag="latest", build_backend=build_backend
        ).build()

        assert captured["context"] == cwd
        assert captured["dockerfile"] is not None
        assert f"WORKDIR /opt/prefect/{cwd.name}/" in captured["dockerfile"]
        assert not (cwd / "Dockerfile").exists()

    @pytest.mark.parametrize("build_backend", ["docker-py", "buildx"])
    def test_relative_context_uses_resolved_directory_name(
        self,
        project: Path,
        mock_build_image: MagicMock,
        mock_buildx_build_image: MagicMock,
        build_backend: Literal["docker-py", "buildx"],
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.chdir(project)
        mock = (
            mock_build_image
            if build_backend == "docker-py"
            else mock_buildx_build_image
        )
        captured = self._capture_dockerfile(mock)

        DockerImage(
            name="test-image", tag="latest", build_backend=build_backend, context="."
        ).build()

        assert captured["dockerfile"] is not None
        assert "WORKDIR /opt/prefect/project/" in captured["dockerfile"]
        assert not (project / "Dockerfile").exists()
