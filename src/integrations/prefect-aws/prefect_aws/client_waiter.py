"""Task for waiting on a long-running AWS job"""

from typing import Any, Dict, Optional

from botocore.waiter import WaiterModel, create_waiter_with_client

from prefect import get_run_logger, task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_aws.credentials import AwsCredentials


@task
async def client_waiter(
    client: str,
    waiter_name: str,
    aws_credentials: AwsCredentials,
    waiter_definition: Optional[Dict[str, Any]] = None,
    **waiter_kwargs: Optional[Dict[str, Any]],
):
    """
    Uses the underlying boto3 waiter functionality.

    Args:
        client: The AWS client on which to wait (e.g., 'client_wait', 'ec2', etc).
        waiter_name: The name of the waiter to instantiate.
            You may also use a custom waiter name, if you supply
            an accompanying waiter definition dict.
        aws_credentials: Credentials to use for authentication with AWS.
        waiter_definition: A valid custom waiter model, as a dict. Note that if
            you supply a custom definition, it is assumed that the provided
            'waiter_name' is contained within the waiter definition dict.
        **waiter_kwargs: Arguments to pass to the `waiter.wait(...)` method. Will
            depend upon the specific waiter being called.

    Example:
        Run an ec2 waiter until instance_exists.
        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.client_wait import client_waiter

        @flow
        def example_client_wait_flow():
            aws_credentials = AwsCredentials(
                aws_access_key_id="acccess_key_id",
                aws_secret_access_key="secret_access_key"
            )

            waiter = client_waiter(
                "ec2",
                "instance_exists",
                aws_credentials
            )

            return waiter
        example_client_wait_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Waiting on %s job", client)

    boto_client = aws_credentials.get_boto3_session().client(client)

    if waiter_definition is not None:
        # Use user-provided waiter definition
        waiter_model = WaiterModel(waiter_definition)
        waiter = create_waiter_with_client(waiter_name, waiter_model, boto_client)
    elif waiter_name in boto_client.waiter_names:
        waiter = boto_client.get_waiter(waiter_name)
    else:
        raise ValueError(
            f"The waiter name, {waiter_name}, is not a valid boto waiter; "
            "if using a custom waiter, you must provide a waiter definition"
        )

    await run_sync_in_worker_thread(waiter.wait, **waiter_kwargs)
