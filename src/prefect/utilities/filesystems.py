import io
import os
from urllib.parse import urlparse
from typing import NamedTuple


class ParsedPath(NamedTuple):
    """A parsed path"""

    scheme: str
    netloc: str
    path: str


def parse_path(path: str) -> ParsedPath:
    """Parse a path into its components.

    Parses a path of the form `[{scheme}://][{netloc}]{path}`, similar to
    `urllib.parse.urlparse`. The main difference is that windows paths with
    `\\` and optional drive designators are supported.

    WARNING: If you pass a Windows path, you must provide a drive and must not provide
             a scheme or the returned `ParsedPath` will have an empty path

    Args:
        - path (str): The path to parse.

    Returns:
        - ParsedPath: the parsed path.
    """
    # On windows, this might be a local path with a drive
    # splitdrive is a no-op on non-windows
    drive, _ = os.path.splitdrive(path)
    if drive:
        scheme = "file"
        netloc = ""
    else:
        parsed = urlparse(path)
        scheme = parsed.scheme or ""
        netloc = parsed.netloc or ""
        path = parsed.path or ""

    if scheme in (None, "", "local"):
        scheme = "file"

    return ParsedPath(scheme, netloc, path)


def read_bytes_from_path(path: str) -> bytes:
    """Read bytes from a given path.

    Paths may be local files, or remote files (given a supported file scheme).

    Args:
        - path (str): The file path

    Returns:
        - bytes: The file contents
    """
    parsed = parse_path(path)
    if not parsed.scheme or parsed.scheme in ("file", "agent"):
        with open(parsed.path, "rb") as f:
            return f.read()
    elif parsed.scheme in {"https", "http"}:
        import requests

        return requests.get(path).content
    elif parsed.scheme in ["gcs", "gs"]:
        from prefect.utilities.gcp import get_storage_client

        client = get_storage_client()
        bucket = client.bucket(parsed.netloc)
        blob = bucket.get_blob(parsed.path.lstrip("/"))
        if blob is None:
            raise ValueError(f"Job template doesn't exist at {path}")
        # Support GCS < 1.31
        return (
            blob.download_as_bytes()
            if hasattr(blob, "download_as_bytes")
            else blob.download_as_string()
        )
    elif parsed.scheme == "s3":
        from prefect.utilities.aws import get_boto_client

        client = get_boto_client(resource="s3")
        stream = io.BytesIO()
        client.download_fileobj(
            Bucket=parsed.netloc, Key=parsed.path.lstrip("/"), Fileobj=stream
        )
        return stream.getvalue()
    else:
        raise ValueError(f"Unsupported file scheme {path}")
