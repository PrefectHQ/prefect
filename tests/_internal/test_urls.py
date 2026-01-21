import pytest

from prefect._internal.urls import strip_auth_from_url


@pytest.mark.parametrize(
    "url,expected",
    [
        # URL with username and password
        (
            "https://user:pass@github.com/org/repo.git",
            "https://github.com/org/repo.git",
        ),
        # URL with only token (as username)
        (
            "https://token@github.com/org/repo.git",
            "https://github.com/org/repo.git",
        ),
        # URL without auth - unchanged
        (
            "https://github.com/org/repo.git",
            "https://github.com/org/repo.git",
        ),
        # URL with port
        (
            "https://user:pass@gitlab.example.com:8443/org/repo.git",
            "https://gitlab.example.com:8443/org/repo.git",
        ),
        # HTTP URL
        (
            "http://token@example.com/repo",
            "http://example.com/repo",
        ),
        # URL with query string
        (
            "https://user:pass@example.com/path?query=1",
            "https://example.com/path?query=1",
        ),
        # URL with fragment
        (
            "https://user:pass@example.com/path#section",
            "https://example.com/path#section",
        ),
        # Empty/malformed URL - returned as-is
        ("", ""),
        ("not-a-url", "not-a-url"),
    ],
)
def test_strip_auth_from_url(url: str, expected: str):
    assert strip_auth_from_url(url) == expected
