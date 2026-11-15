import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

from prefect import __version_info__
from prefect.utilities.dockerutils import (
    ImageBuilder,
    generate_default_dockerfile,
    get_prefect_image_name,
)

# Get the short SHA from git, with fallback to version info
try:
    COMMIT_SHA = (
        subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"])
        .decode("utf-8")
        .strip()
    )
except Exception:
    COMMIT_SHA = __version_info__["full-revisionid"][:7]

PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


@pytest.mark.parametrize(
    "prefect_version, python_version, flavor, expected",
    [
        (
            None,
            None,
            None,
            f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python{PYTHON_VERSION}",
        ),
        (None, "3.9", None, f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python3.9"),
        (None, "3.10", None, f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python3.10"),
        (None, "3.11", None, f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python3.11"),
        (None, "3.12", None, f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python3.12"),
        (
            None,
            None,
            "conda",
            f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python{PYTHON_VERSION}-conda",
        ),
        ("3.0.0", None, None, f"prefecthq/prefect:3.0.0-python{PYTHON_VERSION}"),
        (
            f"3.0.0+1.g{COMMIT_SHA}",
            None,
            None,
            f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python{PYTHON_VERSION}",
        ),
    ],
)
def test_get_prefect_image_name(
    prefect_version: Optional[str],
    python_version: Optional[str],
    flavor: Optional[str],
    expected: str,
):
    assert get_prefect_image_name(prefect_version, python_version, flavor) == expected


@pytest.mark.parametrize(
    "prefect_version, expected",
    [
        # Test that production versions preserve development version info
        ("3.0.0.dev0", f"prefecthq/prefect:3.0.0.dev0-python{PYTHON_VERSION}"),
        ("3.0.0a1", f"prefecthq/prefect:3.0.0a1-python{PYTHON_VERSION}"),
        ("3.0.0b1", f"prefecthq/prefect:3.0.0b1-python{PYTHON_VERSION}"),
        ("3.0.0rc1", f"prefecthq/prefect:3.0.0rc1-python{PYTHON_VERSION}"),
        # Test that local versions still use SHA tagging
        (
            f"3.0.0.dev0+1.g{COMMIT_SHA}",
            f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python{PYTHON_VERSION}",
        ),
        (
            f"3.0.0a1+1.g{COMMIT_SHA}",
            f"prefecthq/prefect-dev:sha-{COMMIT_SHA}-python{PYTHON_VERSION}",
        ),
        # Test stable versions remain unchanged
        ("3.0.0", f"prefecthq/prefect:3.0.0-python{PYTHON_VERSION}"),
        ("2.17.1", f"prefecthq/prefect:2.17.1-python{PYTHON_VERSION}"),
    ],
)
def test_get_prefect_image_name_preserves_dev_version_info(
    prefect_version: str, expected: str
):
    """Test that production builds preserve dev version info instead of stripping it."""
    assert get_prefect_image_name(prefect_version) == expected


@pytest.fixture
def ascii_default_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make writes that omit `encoding` fall back to ASCII.

    CI hosts and most developer machines default to UTF-8, so a write that
    relies on the platform default encoding still succeeds there. Wrapping the
    `pathlib` write entry points used by the Docker utilities reproduces the
    cp936/cp1252 failure on any host, without spawning a child process.
    """
    real_write_text = Path.write_text
    real_open = Path.open

    def write_text(
        self: Path,
        data: str,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> int:
        return real_write_text(
            self, data, encoding=encoding or "ascii", errors=errors, newline=newline
        )

    def open_with_ascii_default(
        self: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> Any:
        if "b" not in mode and encoding is None and any(c in mode for c in "wax+"):
            encoding = "ascii"
        return real_open(
            self,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(Path, "open", open_with_ascii_default)


def test_image_builder_write_text_is_utf8(tmp_path: Path, ascii_default_encoding: None):
    """Context files must be UTF-8 even when the default encoding is not."""
    text = "print('emoji 🔥')\n"
    builder = ImageBuilder(base_image="python:3.11", context=tmp_path)
    builder.write_text(text, "app.py")

    written = [path for path in tmp_path.iterdir() if path.is_file()]
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == text


def test_image_builder_build_writes_utf8_dockerfile(
    tmp_path: Path,
    ascii_default_encoding: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """The Dockerfile written by `build` must not use the default encoding."""
    written: list[str] = []

    def fake_build_image(context: Path, *args: Any, **kwargs: Any) -> str:
        # build() unlinks the Dockerfile after handing the context to Docker,
        # so read it back while the build is still in progress.
        written.append((context / "Dockerfile").read_text(encoding="utf-8"))
        return "image-id"

    monkeypatch.setattr("prefect.utilities.dockerutils.build_image", fake_build_image)
    builder = ImageBuilder(base_image="python:3.11", context=tmp_path)
    builder.add_line("RUN echo 'emoji 🔥'")

    assert builder.build() == "image-id"
    assert written == ["FROM python:3.11\nRUN echo 'emoji 🔥'\n"]


def test_generate_default_dockerfile_is_utf8(
    tmp_path: Path, ascii_default_encoding: None
):
    """The default Dockerfile must stay UTF-8 for a non-ASCII context path."""
    context = tmp_path / "项目"
    context.mkdir()

    with generate_default_dockerfile(context=context) as dockerfile:
        contents = dockerfile.read_text(encoding="utf-8")

    assert f"COPY . /opt/prefect/{context.name}/" in contents
