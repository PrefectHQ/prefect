import ipaddress
import socket
from urllib.parse import urlparse


def validate_restricted_url(url: str):
    """
    Validate that the provided URL is safe for outbound requests.  This prevents
    attacks like SSRF (Server Side Request Forgery), where an attacker can make
    requests to internal services (like the GCP metadata service, localhost addresses,
    or in-cluster Kubernetes services)
    Args:
        url: The URL to validate.
    Raises:
        ValueError: If the URL is a restricted URL.
    """

    try:
        parsed_url = urlparse(url)
    except ValueError:
        raise ValueError(f"{url!r} is not a valid URL.")

    if parsed_url.scheme not in ("http", "https"):
        raise ValueError(
            f"{url!r} is not a valid URL.  Only HTTP and HTTPS URLs are allowed."
        )

    hostname = parsed_url.hostname or ""

    # Remove IPv6 brackets if present
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]

    if not hostname:
        raise ValueError(f"{url!r} is not a valid URL.")

    try:
        ip_address = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_address)
    except socket.gaierror:
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            raise ValueError(f"{url!r} is not a valid URL.  It could not be resolved.")

    if ip.is_private:
        raise ValueError(
            f"{url!r} is not a valid URL.  It resolves to the private address {ip}."
        )
