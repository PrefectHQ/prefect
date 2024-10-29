import pytest

from prefect.utilities.urls import validate_restricted_url

RESTRICTED_URLS = [
    ("", ""),
    (" ", ""),
    ("[]", ""),
    ("not a url", ""),
    ("http://", ""),
    ("https://", ""),
    ("http://[]/foo/bar", ""),
    ("ftp://example.com", "HTTP and HTTPS"),
    ("gopher://example.com", "HTTP and HTTPS"),
    ("https://localhost", "private address"),
    ("https://127.0.0.1", "private address"),
    ("https://[::1]", "private address"),
    ("https://[fc00:1234:5678:9abc::10]", "private address"),
    ("https://[fd12:3456:789a:1::1]", "private address"),
    ("https://[fe80::1234:5678:9abc]", "private address"),
    ("https://10.0.0.1", "private address"),
    ("https://10.255.255.255", "private address"),
    ("https://172.16.0.1", "private address"),
    ("https://172.31.255.255", "private address"),
    ("https://192.168.1.1", "private address"),
    ("https://192.168.1.255", "private address"),
    ("https://169.254.0.1", "private address"),
    ("https://169.254.169.254", "private address"),
    ("https://169.254.254.255", "private address"),
    # These will resolve to a private address in production, but not in tests,
    # so we'll use "resolve" as the reason to catch both cases
    ("https://metadata.google.internal", "resolve"),
    ("https://anything.privatecloud", "resolve"),
    ("https://anything.privatecloud.svc", "resolve"),
    ("https://anything.privatecloud.svc.cluster.local", "resolve"),
    ("https://cluster-internal", "resolve"),
    ("https://network-internal.cloud.svc", "resolve"),
    ("https://private-internal.cloud.svc.cluster.local", "resolve"),
]


@pytest.mark.parametrize("value, reason", RESTRICTED_URLS)
def test_validate_restricted_url_validates(value: str, reason: str):
    with pytest.raises(ValueError, match=f"is not a valid URL.*{reason}"):
        validate_restricted_url(url=value)
