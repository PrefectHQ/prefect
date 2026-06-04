import pytest

from prefect._internal.urls import strip_auth_from_url, strip_auth_from_urls_in_text


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "fatal: could not read Username for 'https://github.com'",
            "fatal: could not read Username for 'https://github.com'",
        ),
        (
            "fatal: unable to access 'https://ghp_abc123@github.com/org/repo.git/'",
            "fatal: unable to access 'https://github.com/org/repo.git/'",
        ),
        (
            "error for https://user:secret@gitlab.com/path and https://tok@example.com/x",
            "error for https://gitlab.com/path and https://example.com/x",
        ),
        (
            "fatal: Authentication failed for "
            "'https://oauth2:p@ss:word#1@gitlab.com/PrefectHQ/prefect.git/'",
            "fatal: Authentication failed for "
            "'https://gitlab.com/PrefectHQ/prefect.git/'",
        ),
        ("", ""),
        ("no urls here", "no urls here"),
    ],
)
def test_strip_auth_from_urls_in_text(raw: str, expected: str):
    assert strip_auth_from_urls_in_text(raw) == expected


def test_strip_auth_from_urls_in_text_redacts_extra_secrets():
    text = "remote: token=ghp_abc123 hit rate limit"
    assert (
        strip_auth_from_urls_in_text(text, extra_secrets=["ghp_abc123"])
        == "remote: token=*** hit rate limit"
    )


def test_strip_auth_from_url_handles_malformed_credential_url():
    assert (
        strip_auth_from_url(
            "https://oauth2:p@ss:word#1@gitlab.com/PrefectHQ/prefect.git/"
        )
        == "https://gitlab.com/PrefectHQ/prefect.git/"
    )
