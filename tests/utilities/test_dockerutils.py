import subprocess
import sys
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
