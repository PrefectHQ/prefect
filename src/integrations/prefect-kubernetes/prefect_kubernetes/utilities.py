"""Utilities for working with the Python Kubernetes API."""

import socket
import sys
from typing import Optional, TypeVar

from aiohttp import ClientResponse
from aiohttp.client_reqrep import ClientRequest
from aiohttp.connector import Connection
from slugify import slugify

# Note: `dict(str, str)` is the Kubernetes API convention for
# representing an OpenAPI `dict` with `str` keys and values.
base_types = {"str", "int", "float", "bool", "list[str]", "dict(str, str)", "object"}

V1KubernetesModel = TypeVar("V1KubernetesModel")


class KeepAliveClientRequest(ClientRequest):
    """
    aiohttp only directly implements socket keepalive for incoming connections
    in its RequestHandler. For client connections, we need to set the keepalive
    ourselves.
    Refer to https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-759205696
    """

    async def send(self, conn: Connection) -> ClientResponse:
        sock = conn.protocol.transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)

        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 6)

        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)

        if sys.platform == "darwin":
            # TCP_KEEP_ALIVE not available on socket module in macOS, but defined in
            # https://github.com/apple/darwin-xnu/blob/2ff845c2e033bd0ff64b5b6aa6063a1f8f65aa32/bsd/netinet/tcp.h#L215
            TCP_KEEP_ALIVE = 0x10
            sock.setsockopt(socket.IPPROTO_TCP, TCP_KEEP_ALIVE, 30)

        return await super().send(conn)


def _slugify_name(name: str, max_length: int = 45) -> Optional[str]:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 45 chars.

    The 45 character length allows room for the k8s utility
    "generateName" to generate a unique name from the slug while
    keeping the total length of a name below 63 characters, which is
    the limit for e.g. label names that follow RFC 1123 (hostnames) and
    RFC 1035 (domain names).

    Args:
        name: The name of the job

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,  # Leave enough space for generateName
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None


def _slugify_label_key(key: str, max_length: int = 63, prefix_max_length=253) -> str:
    """
    Slugify text for use as a label key.

    Keys are composed of an optional prefix and name, separated by a slash (/).

    Keeps only alphanumeric characters, dashes, underscores, and periods.
    Limits the length of the label prefix to 253 characters.
    Limits the length of the label name to 63 characters.

    See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

    Args:
        key: The label key

    Returns:
        The slugified label key
    """  # noqa
    if "/" in key:
        prefix, name = key.split("/", maxsplit=1)
    else:
        prefix = None
        name = key

    name_slug = (
        slugify(name, max_length=max_length, regex_pattern=r"[^a-zA-Z0-9-_.]+").strip(
            "_-."  # Must start or end with alphanumeric characters
        )
        or name
    )
    # Fallback to the original if we end up with an empty slug, this will allow
    # Kubernetes to throw the validation error

    if prefix:
        prefix_slug = (
            slugify(
                prefix,
                max_length=prefix_max_length,
                regex_pattern=r"[^a-zA-Z0-9-\.]+",
            ).strip("_-.")  # Must start or end with alphanumeric characters
            or prefix
        )

        return f"{prefix_slug}/{name_slug}"

    return name_slug


def _slugify_label_value(value: str, max_length: int = 63) -> str:
    """
    Slugify text for use as a label value.

    Keeps only alphanumeric characters, dashes, underscores, and periods.
    Limits the total length of label text to below 63 characters.

    See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

    Args:
        value: The text for the label

    Returns:
        The slugified value
    """  # noqa
    slug = (
        slugify(value, max_length=max_length, regex_pattern=r"[^a-zA-Z0-9-_\.]+").strip(
            "_-."  # Must start or end with alphanumeric characters
        )
        or value
    )
    # Fallback to the original if we end up with an empty slug, this will allow
    # Kubernetes to throw the validation error

    return slug
