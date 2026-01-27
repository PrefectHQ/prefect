import sys

import pytest

from prefect._internal.compatibility.backports import tomllib

min_python_version = (3, 11)


@pytest.fixture(scope="session")
def toml1_0_content() -> str:
    return """\
[dependency-groups]
dev = [
    "dummy-dependency~=1.2.0",
    {include-group = "dummy-group-name"},
]
"""


@pytest.mark.skipif(
    sys.version_info < min_python_version,
    reason=f"Test requires Python version {min_python_version[0]}.{min_python_version[1]} or higher",
)
def test_can_parse_toml1_0_on_python311_plus(toml1_0_content):
    assert tomllib.loads(toml1_0_content)


@pytest.mark.skipif(
    sys.version_info >= min_python_version,
    reason=f"Test requires Python version less than {min_python_version[0]}.{min_python_version[1]}",
)
def test_error_parsing_toml1_0_before_python311(toml1_0_content):
    with pytest.raises(IndexError):
        tomllib.loads(toml1_0_content)
