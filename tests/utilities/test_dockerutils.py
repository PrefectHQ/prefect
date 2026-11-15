import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

from prefect import __version_info__
from prefect.utilities.dockerutils import get_prefect_image_name

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


def test_image_builder_write_text_is_utf8(tmp_path: Path):
    """Non-ASCII context files must not depend on the platform default encoding."""
    from prefect.utilities.dockerutils import ImageBuilder

    text = "print('emoji 🔥')\n"
    builder = ImageBuilder(base_image="python:3.11", context=tmp_path)
    builder.write_text(text, "app.py")

    written = [path for path in tmp_path.iterdir() if path.is_file()]
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == text


def test_image_builder_write_text_under_an_ascii_locale(tmp_path: Path):
    """The same write in a child process whose default encoding is ASCII."""
    script = (
        "from pathlib import Path\n"
        "from prefect.utilities.dockerutils import ImageBuilder\n"
        "context = Path.cwd()\n"
        "builder = ImageBuilder(base_image='python:3.11', context=context)\n"
        "builder.write_text(\"print('emoji \\U0001f525')\\n\", 'app.py')\n"
        "print('context written')\n"
    )
    # The child runs with cwd=tmp_path and resolves the context with
    # Path.cwd(), so a non-ASCII temp root never reaches this source. The
    # interpreter decodes the -c argument with the filesystem encoding, so a
    # literal non-ASCII character here would abort the child before it imports.
    assert script.isascii()

    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "context written" in completed.stdout

    written = [path for path in tmp_path.iterdir() if path.is_file()]
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == "print('emoji 🔥')\n"
    # The bytes on disk are the UTF-8 encoding of the emoji, not an escape.
    assert b"\xf0\x9f\x94\xa5" in written[0].read_bytes()
