import packaging.version
import pytest

from prefect.utilities.dockerutils import (
    format_outlier_version_name,
    parse_image_tag,
    split_repository_path,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("localhost/simpleimage", ("localhost/simpleimage", None)),
        ("localhost/simpleimage:2.1.1", ("localhost/simpleimage", "2.1.1")),
        ("prefecthq/prefect", ("prefecthq/prefect", None)),
        ("prefecthq/prefect:2.1.1", ("prefecthq/prefect", "2.1.1")),
        ("simpleimage", ("simpleimage", None)),
        ("simpleimage:2.1.1", ("simpleimage", "2.1.1")),
        ("hostname.io/dir/subdir", ("hostname.io/dir/subdir", None)),
        ("hostname.io/dir/subdir:latest", ("hostname.io/dir/subdir", "latest")),
        ("hostname.io:5050/dir/subdir", ("hostname.io:5050/dir/subdir", None)),
        (
            "hostname.io:5050/dir/subdir:latest",
            ("hostname.io:5050/dir/subdir", "latest"),
        ),
        (
            "prefecthq/prefect@sha256:abcdef1234567890",
            ("prefecthq/prefect", "sha256:abcdef1234567890"),
        ),
    ],
)
def test_parse_image_tag(value, expected):
    assert parse_image_tag(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("20.10.0", "20.10.0"),
        ("v20.10.10", "v20.10.10"),
        ("v20.10.0-ce", "v20.10.0"),
        ("v20.10.10-ee", "v20.10.10"),
        ("20.10.0-ce", "20.10.0"),
        ("20.10.10-ee", "20.10.10"),
    ],
)
def test_format_outlier_version_name(value, expected):
    version = format_outlier_version_name(value)
    # Basic test
    assert version == expected
    # Confirm return value can be parsed
    assert isinstance(packaging.version.parse(version), packaging.version.Version)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("localhost/simpleimage", ("localhost", "simpleimage")),
        ("localhost/simpleimage:2.1.1", ("localhost", "simpleimage:2.1.1")),
        ("prefecthq/prefect", ("prefecthq", "prefect")),
        ("prefecthq/prefect:2.1.1", ("prefecthq", "prefect:2.1.1")),
        ("simpleimage", (None, "simpleimage")),
        ("simpleimage:2.1.1", (None, "simpleimage:2.1.1")),
        ("hostname.io/dir/subdir", ("hostname.io/dir", "subdir")),
        ("hostname.io/dir/subdir:latest", ("hostname.io/dir", "subdir:latest")),
        ("hostname.io:5050/dir/subdir", ("hostname.io:5050/dir", "subdir")),
        (
            "hostname.io:5050/dir/subdir:latest",
            ("hostname.io:5050/dir", "subdir:latest"),
        ),
    ],
)
def test_split_repository_path(value, expected):
    assert split_repository_path(value) == expected
