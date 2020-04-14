"""
Utility functions for interacting with Google Cloud.
"""
import prefect

import boto3


def get_boto_client(resource: str, credentials: dict = None) -> "boto3.client":
    """
    Utility function for loading boto3 client objects from a given set of credentials.

    Args:
        - resource (str): the name of the resource to retrieve a client for
        - credentials (dict, optional): a dictionary of Google credentials used to initialize the Client; if
            not provided, will attempt to load the Client using ambient environment settings

    Returns:
        - Client: an initialized and authenticated Google Client
    """
    aws_access_key = None
    aws_secret_access_key = None

    if credentials:
        aws_access_key = credentials["ACCESS_KEY"]
        aws_secret_access_key = credentials["SECRET_ACCESS_KEY"]
    else:
        ctx_credentials = prefect.context.get("secrets", {}).get("AWS_CREDENTIALS", {})
        aws_access_key = ctx_credentials.get("ACCESS_KEY")
        aws_secret_access_key = ctx_credentials.get("SECRET_ACCESS_KEY")

    return boto3.client(
        resource,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_access_key,
    )
