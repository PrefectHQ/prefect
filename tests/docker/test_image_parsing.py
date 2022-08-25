import pytest

from prefect.docker import parse_image_tag


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
