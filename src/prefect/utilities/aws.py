"""
Utility functions for interacting with AWS.
"""
import prefect

import boto3
from typing import Any, Optional


def get_boto_client(
    resource: str,
    credentials: Optional[dict] = None,
    use_session: Optional[bool] = False,
    profile_name: Optional[str] = None,
    **kwargs: Any
) -> "boto3.client":
    """
    Utility function for loading boto3 client objects from a given set of credentials.

    Args:
        - resource (str): the name of the resource to retrieve a client for
        - credentials (dict, optional): a dictionary of AWS credentials used to
            initialize the Client; if not provided, will attempt to load the
            Client using ambient environment settings
        - use_session (bool, optional): a boolean specifying whether to load
            this client using a session or not; defaults to `False`
        - profile_name (str, optional): The name of a profile to use.
        - **kwargs (Any, optional): additional keyword arguments to pass to boto3

    Returns:
        - Client: an initialized and authenticated boto3 Client
    """

    if profile_name and not use_session:
        raise ValueError(
            "profile_name can only be used with the boto3.session. Please set use_session=True"
        )

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

    if use_session:
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html?#multithreading-multiprocessing  # noqa
        region_name = kwargs.pop("region_name", None)
        botocore_session = kwargs.pop("botocore_session", None)
        session = boto3.session.Session(
            profile_name=profile_name,
            region_name=region_name,
            botocore_session=botocore_session,
        )
        return session.client(
            resource,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            **kwargs
        )
    else:
        return boto3.client(
            resource,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            **kwargs
        )
