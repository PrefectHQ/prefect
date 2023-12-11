import packaging.version
import pytest

from prefect.utilities.dockerutils import (
    format_outlier_version_name,
    join_repository_path,
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
        ("localhost/simpleimage", (None, "localhost", "simpleimage")),
        ("localhost/simpleimage:2.1.1", (None, "localhost", "simpleimage:2.1.1")),
        ("prefecthq/prefect", (None, "prefecthq", "prefect")),
        ("prefecthq/prefect:2.1.1", (None, "prefecthq", "prefect:2.1.1")),
        ("simpleimage", (None, None, "simpleimage")),
        ("simpleimage:2.1.1", (None, None, "simpleimage:2.1.1")),
        ("hostname.io/dir/subdir", ("hostname.io", "dir", "subdir")),
        ("hostname.io/dir/subdir:latest", ("hostname.io", "dir", "subdir:latest")),
        ("hostname.io:5050/dir/subdir", ("hostname.io:5050", "dir", "subdir")),
        (
            "hostname.io:5050/dir/subdir:latest",
            ("hostname.io:5050", "dir", "subdir:latest"),
        ),
    ],
)
def test_split_repository_path(value, expected):
    assert split_repository_path(value) == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (("simpleimage", "localhost"), "localhost/simpleimage"),
        (("simpleimage:2.1.1", "localhost"), "localhost/simpleimage:2.1.1"),
        (("prefect", "prefecthq"), "prefecthq/prefect"),
        (("prefect:2.1.1", "prefecthq"), "prefecthq/prefect:2.1.1"),
        (("simpleimage",), "simpleimage"),
        (("simpleimage:2.1.1",), "simpleimage:2.1.1"),
        (("subdir", "dir", "hostname.io"), "hostname.io/dir/subdir"),
        (
            (
                "subdir:latest",
                "dir",
                "hostname.io",
            ),
            "hostname.io/dir/subdir:latest",
        ),
        (
            (
                "subdir",
                "dir",
                "hostname.io:5050",
            ),
            "hostname.io:5050/dir/subdir",
        ),
        (
            (
                "subdir:latest",
                "dir",
                "hostname.io:5050",
            ),
            "hostname.io:5050/dir/subdir:latest",
        ),
    ],
)
def test_join_repository_path(args, expected):
    assert join_repository_path(*args) == expected
