from urllib.parse import urlparse, urlunparse


def strip_auth_from_url(url: str) -> str:
    """
    Remove authentication credentials (username/password) from a URL.

    Useful for sanitizing URLs before including them in error messages
    or logs to avoid leaking secrets.
    """
    parsed = urlparse(url)

    if not parsed.hostname:
        return url

    netloc = parsed.hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
