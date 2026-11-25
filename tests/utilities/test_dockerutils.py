import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

from prefect import __version_info__
from prefect.utilities.dockerutils import ImageBuilder, get_prefect_image_name

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


NON_ASCII_TEXT = "print('emoji \U0001f525')\n"

# Runs the child interpreter with an ASCII default encoding, the same failure mode
# as a cp936/cp1252 Windows host
ASCII_LOCALE_ENV = {
    "LC_ALL": "C",
    "LANG": "C",
    "PYTHONUTF8": "0",
    "PYTHONCOERCECLOCALE": "0",
}

ASSERT_ASCII_LOCALE = """
import codecs, locale
assert codecs.lookup(locale.getpreferredencoding(False)).name != "utf-8"
"""


def run_under_ascii_locale(script: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", ASSERT_ASCII_LOCALE + script, *args],
        env={**os.environ, **ASCII_LOCALE_ENV},
        capture_output=True,
        text=True,
        errors="replace",
    )
    assert result.returncode == 0, result.stderr


class TestImageBuilderEncoding:
    def test_write_text_writes_utf8(self, tmp_path: Path):
        builder = ImageBuilder(base_image="python:3.12", context=tmp_path)
        builder.write_text(NON_ASCII_TEXT, "app.py")

        (written,) = tmp_path.iterdir()
        assert written.read_bytes() == NON_ASCII_TEXT.encode("utf-8")

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Locale environment variables are POSIX-only"
    )
    def test_write_text_writes_utf8_under_ascii_locale(self, tmp_path: Path):
        run_under_ascii_locale(
            """
import sys
from pathlib import Path
from prefect.utilities.dockerutils import ImageBuilder

builder = ImageBuilder(base_image="python:3.12", context=Path(sys.argv[1]))
builder.write_text("print('emoji \\U0001f525')\\n", "app.py")
""",
            str(tmp_path),
        )

        (written,) = tmp_path.iterdir()
        assert written.read_bytes() == NON_ASCII_TEXT.encode("utf-8")

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Locale environment variables are POSIX-only"
    )
    def test_build_writes_utf8_dockerfile_under_ascii_locale(self, tmp_path: Path):
        output = tmp_path / "Dockerfile.captured"
        run_under_ascii_locale(
            """
import sys
from pathlib import Path
from unittest import mock
from prefect.utilities.dockerutils import ImageBuilder

captured = {}

def fake_build_image(context, **kwargs):
    captured["dockerfile"] = (context / "Dockerfile").read_bytes()
    return "image-id"

with mock.patch("prefect.utilities.dockerutils.build_image", fake_build_image):
    with ImageBuilder("python:3.12") as builder:
        builder.add_line("LABEL description=\\"\\U0001f525\\"")
        builder.build()

Path(sys.argv[1]).write_bytes(captured["dockerfile"])
""",
            str(output),
        )

        assert output.read_bytes() == (
            'FROM python:3.12\nLABEL description="\U0001f525"\n'.encode("utf-8")
        )
