"""
Utility functions for interacting with AWS.
"""
import threading
import warnings
import weakref

import prefect

import boto3
from typing import TYPE_CHECKING, Any, Optional, MutableMapping

if TYPE_CHECKING:
    import botocore.client


_CLIENT_CACHE = (
    weakref.WeakValueDictionary()
)  # type: MutableMapping[tuple, botocore.client.BaseClient]
_LOCK = threading.Lock()


def get_boto_client(
    resource: str,
    credentials: Optional[dict] = None,
    region_name: Optional[str] = None,
    profile_name: Optional[str] = None,
    **kwargs: Any
) -> "botocore.client.BaseClient":
    """
    Utility function for loading boto3 client objects from a given set of credentials.

    Note: this utility is threadsafe, and will cache _active_ clients to be
    potentially reused by other concurrent callers, reducing the overhead of
    client creation.

    Args:
        - resource (str): the name of the resource to retrieve a client for
        - credentials (dict, optional): a dictionary of AWS credentials used to
            initialize the Client; if not provided, will attempt to load the
            Client using ambient environment settings
        - region_name (str, optional): The aws region name to use, defaults to your
            global configured default.
        - profile_name (str, optional): The name of a boto3 profile to use.
        - **kwargs (Any, optional): additional keyword arguments to pass to boto3

    Returns:
        - Client: an initialized and authenticated boto3 Client
    """

    if kwargs.pop("use_session", None) is not None:
        # Deprecated in 0.14.9
        warnings.warn(
            "The `use_session` kwarg has been deprecated, prefect now infers "
            "whether a new boto session should be used automatically."
        )

    botocore_session = kwargs.pop("botocore_session", None)

    if credentials:
        aws_access_key = credentials["ACCESS_KEY"]
        aws_secret_access_key = credentials["SECRET_ACCESS_KEY"]
        aws_session_token = credentials.get("SESSION_TOKEN")
    else:
        ctx_credentials = prefect.context.get("secrets", {}).get("AWS_CREDENTIALS", {})
        aws_access_key = ctx_credentials.get("ACCESS_KEY")
        aws_secret_access_key = ctx_credentials.get("SECRET_ACCESS_KEY")
        aws_session_token = ctx_credentials.get("SESSION_TOKEN")

    kwargs_access_key_id = kwargs.pop("aws_access_key_id", None)
    kwargs_secret_access_key = kwargs.pop("aws_secret_access_key", None)
    kwargs_session_token = kwargs.pop("aws_session_token", None)

    aws_access_key = aws_access_key or kwargs_access_key_id
    aws_secret_access_key = aws_secret_access_key or kwargs_secret_access_key
    aws_session_token = aws_session_token or kwargs_session_token

    # Boto3 clients _are_ threadsafe, but the creation of a client or a session
    # isn't thread safe. Creating a client has a small cost (~5-10 ms), while a
    # session has a larger cost (50-120 ms). Creating a new session also
    # renegotiates auth - apparently AWS can throttle these requests if there
    # are too many of them, so we really want to minimize session creation if
    # we can.
    #
    # We keep a weakref cache of clients around to minimize recreation, and use
    # a global lock to synchronize access to this cache. Unfortunately a client
    # doesn't keep a ref around to its backing session, so we can't (easily)
    # keep a cache of sessions around. Most users should use only a single
    # session per process though, and boto3 already supports that with a global
    # shared session. In practice this is much more efficient than creating a
    # new AWS session for every request, and still maintains thread safety.
    with _LOCK:
        botocore_session = kwargs.pop("botocore_session", None)
        cache_key = (
            profile_name,
            region_name,
            id(botocore_session),
            resource,
            aws_access_key,
            aws_secret_access_key,
            aws_session_token,
        )

        # If no extra kwargs and client already created, use the cached client
        if not kwargs and cache_key in _CLIENT_CACHE:
            return _CLIENT_CACHE[cache_key]

        if profile_name or botocore_session:
            session = boto3.session.Session(
                profile_name=profile_name,
                region_name=region_name,
                botocore_session=botocore_session,
            )
        else:
            session = boto3

        client = session.client(
            resource,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
            **kwargs,
        )
        # Cache the client if no extra kwargs
        if not kwargs:
            _CLIENT_CACHE[cache_key] = client

    return client
