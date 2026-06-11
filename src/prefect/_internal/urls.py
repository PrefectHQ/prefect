import re
from collections.abc import Iterable
from urllib.parse import urlparse, urlunparse

_URL_AUTH_PATTERN = re.compile(
    r"(?P<scheme>https?://)[^/\s'\"<>]*@", flags=re.IGNORECASE
)


def strip_auth_from_url(url: str) -> str:
    """
    Remove authentication credentials (username/password) from a URL.

    Useful for sanitizing URLs before including them in error messages
    or logs to avoid leaking secrets.
    """
    try:
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
    except ValueError:
        return strip_auth_from_urls_in_text(url)


def strip_auth_from_urls_in_text(
    text: str, extra_secrets: Iterable[str] | None = None
) -> str:
    """
    Remove authentication credentials from HTTP(S) URLs embedded in text.

    Useful for sanitizing command output before including it in error messages
    or logs. Any caller-supplied secrets are replaced with a redaction marker.
    """
    if not text:
        return text

    sanitized = _URL_AUTH_PATTERN.sub(r"\g<scheme>", text)
    for secret in extra_secrets or ():
        if secret:
            sanitized = sanitized.replace(secret, "***")
    return sanitized
