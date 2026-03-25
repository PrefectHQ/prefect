"""Unit tests for the buildx backend module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prefect.docker.buildx import (
    _import_python_on_whales,
    buildx_build_image,
    buildx_push_image,
)
from prefect.utilities.dockerutils import IMAGE_LABELS, BuildError


class TestImportGuard:
    def test_raises_helpful_error_when_python_on_whales_missing(self):
        with patch.dict("sys.modules", {"python_on_whales": None}):
            with pytest.raises(ImportError, match="python-on-whales"):
                _import_python_on_whales()

    def test_returns_module_when_installed(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"python_on_whales": mock_module}):
            result = _import_python_on_whales()
            assert result is mock_module


class TestBuildxBuildImage:
    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_basic_build(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        result = buildx_build_image(
            context=tmp_path,
            dockerfile="Dockerfile",
            tag="test:latest",
        )

        assert result == "sha256:abc123"
        mock_pow.docker.buildx.build.assert_called_once()
        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["context_path"] == str(tmp_path)
        assert call_kwargs["tags"] == ["test:latest"]
        assert call_kwargs["push"] is False

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_labels_are_applied(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(context=tmp_path, tag="test:latest")

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        for key, value in IMAGE_LABELS.items():
            assert call_kwargs["labels"][key] == value

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_custom_labels_merged_with_image_labels(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(
            context=tmp_path,
            tag="test:latest",
            labels={"custom.label": "value"},
        )

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["labels"]["custom.label"] == "value"
        for key, value in IMAGE_LABELS.items():
            assert call_kwargs["labels"][key] == value

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_kwargs_passthrough(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(
            context=tmp_path,
            tag="test:latest",
            secrets=["id=mysecret,src=secret.txt"],
            ssh="default",
            cache_from=["type=registry,ref=myregistry/myimage:cache"],
            cache_to=["type=inline"],
        )

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["secrets"] == ["id=mysecret,src=secret.txt"]
        assert call_kwargs["ssh"] == "default"
        assert call_kwargs["cache_from"] == [
            "type=registry,ref=myregistry/myimage:cache"
        ]
        assert call_kwargs["cache_to"] == ["type=inline"]

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_single_platform_build(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(
            context=tmp_path,
            tag="test:latest",
            platform="linux/amd64",
        )

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["platforms"] == ["linux/amd64"]

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_multi_platform_requires_push(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow

        with pytest.raises(ValueError, match="Multi-platform builds require push=True"):
            buildx_build_image(
                context=tmp_path,
                tag="test:latest",
                platforms=["linux/amd64", "linux/arm64"],
                push=False,
            )

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_multi_platform_with_push(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_pow.docker.buildx.build.return_value = None

        result = buildx_build_image(
            context=tmp_path,
            tag="registry/repo:latest",
            platforms=["linux/amd64", "linux/arm64"],
            push=True,
        )

        assert result == "registry/repo:latest"
        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["push"] is True
        assert call_kwargs["platforms"] == ["linux/amd64", "linux/arm64"]

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_build_error_is_raised(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_pow.exceptions.DockerException = Exception
        mock_pow.docker.buildx.build.side_effect = Exception("build failed")

        with pytest.raises(BuildError, match="build failed"):
            buildx_build_image(context=tmp_path, tag="test:latest")

    def test_requires_context(self):
        with pytest.raises(ValueError, match="context required"):
            buildx_build_image(context=None, tag="test:latest")

    def test_requires_existing_context(self, tmp_path: Path):
        with pytest.raises(ValueError, match="does not exist"):
            buildx_build_image(context=tmp_path / "nonexistent", tag="test:latest")

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_push_build(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(
            context=tmp_path,
            tag="registry/repo:latest",
            push=True,
        )

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert call_kwargs["push"] is True

    @patch("prefect.docker.buildx._import_python_on_whales")
    @patch("prefect.docker.buildx.time.sleep")
    def test_retries_on_transient_error(self, mock_sleep, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.exceptions.DockerException = Exception
        mock_pow.docker.buildx.build.side_effect = [
            Exception("502 Bad Gateway"),
            mock_image,
        ]

        result = buildx_build_image(context=tmp_path, tag="test:latest")

        assert result == "sha256:abc123"
        assert mock_pow.docker.buildx.build.call_count == 2
        mock_sleep.assert_called_once()

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_decode_kwarg_stripped(self, mock_import, tmp_path: Path):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_pow.docker.buildx.build.return_value = mock_image

        buildx_build_image(context=tmp_path, tag="test:latest", decode=True)

        call_kwargs = mock_pow.docker.buildx.build.call_args[1]
        assert "decode" not in call_kwargs


class TestBuildxPushImage:
    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_push_image(self, mock_import):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow

        buildx_push_image(name="registry/repo", tag="latest")

        mock_pow.docker.image.push.assert_called_once_with("registry/repo:latest")

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_push_image_without_tag(self, mock_import):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow

        buildx_push_image(name="registry/repo")

        mock_pow.docker.image.push.assert_called_once_with("registry/repo")

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_push_raises_on_error(self, mock_import):
        mock_pow = MagicMock()
        mock_import.return_value = mock_pow
        mock_pow.exceptions.DockerException = Exception
        mock_pow.docker.image.push.side_effect = Exception("push failed")

        with pytest.raises(OSError, match="push failed"):
            buildx_push_image(name="registry/repo", tag="latest")

    @patch("prefect.docker.buildx._import_python_on_whales")
    def test_push_streams_progress(self, mock_import):
        import io

        mock_pow = MagicMock()
        mock_import.return_value = mock_pow

        stream = io.StringIO()
        buildx_push_image(name="registry/repo", tag="latest", stream_progress_to=stream)

        output = stream.getvalue()
        assert "Pushing registry/repo:latest" in output
        assert "Pushed registry/repo:latest" in output
