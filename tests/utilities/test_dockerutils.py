import sys
from typing import Optional

import pytest

from prefect import __version_info__
from prefect.utilities.dockerutils import get_prefect_image_name

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
            "3.0.0.post0.dev1",
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
