"""Tasks for interacting with AWS Secrets Manager"""

from typing import Any, Dict, List, Optional, Union

from botocore.exceptions import ClientError
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import get_run_logger, task
from prefect.blocks.abstract import SecretBlock
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect_aws import AwsCredentials


@task
async def read_secret(
    secret_name: str,
    aws_credentials: AwsCredentials,
    version_id: Optional[str] = None,
    version_stage: Optional[str] = None,
) -> Union[str, bytes]:
    """
    Reads the value of a given secret from AWS Secrets Manager.

    Args:
        secret_name: Name of stored secret.
        aws_credentials: Credentials to use for authentication with AWS.
        version_id: Specifies version of secret to read. Defaults to the most recent
            version if not given.
        version_stage: Specifies the version stage of the secret to read. Defaults to
            AWS_CURRENT if not given.

    Returns:
        The secret values as a `str` or `bytes` depending on the format in which the
            secret was stored.

    Example:
        Read a secret value:

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.secrets_manager import read_secret

        @flow
        def example_read_secret():
            aws_credentials = AwsCredentials(
                aws_access_key_id="access_key_id",
                aws_secret_access_key="secret_access_key"
            )
            secret_value = read_secret(
                secret_name="db_password",
                aws_credentials=aws_credentials
            )

        example_read_secret()
        ```
    """
    logger = get_run_logger()
    logger.info("Getting value for secret %s", secret_name)

    client = aws_credentials.get_boto3_session().client("secretsmanager")

    get_secret_value_kwargs = dict(SecretId=secret_name)
    if version_id is not None:
        get_secret_value_kwargs["VersionId"] = version_id
    if version_stage is not None:
        get_secret_value_kwargs["VersionStage"] = version_stage

    try:
        response = await run_sync_in_worker_thread(
            client.get_secret_value, **get_secret_value_kwargs
        )
    except ClientError:
        logger.exception("Unable to get value for secret %s", secret_name)
        raise
    else:
        return response.get("SecretString") or response.get("SecretBinary")


@task
async def update_secret(
    secret_name: str,
    secret_value: Union[str, bytes],
    aws_credentials: AwsCredentials,
    description: Optional[str] = None,
) -> Dict[str, str]:
    """
    Updates the value of a given secret in AWS Secrets Manager.

    Args:
        secret_name: Name of secret to update.
        secret_value: Desired value of the secret. Can be either `str` or `bytes`.
        aws_credentials: Credentials to use for authentication with AWS.
        description: Desired description of the secret.

    Returns:
        A dict containing the secret ARN (Amazon Resource Name),
            name, and current version ID.
            ```python
            {
                "ARN": str,
                "Name": str,
                "VersionId": str
            }
            ```

    Example:
        Update a secret value:

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.secrets_manager import update_secret

        @flow
        def example_update_secret():
            aws_credentials = AwsCredentials(
                aws_access_key_id="access_key_id",
                aws_secret_access_key="secret_access_key"
            )
            update_secret(
                secret_name="life_the_universe_and_everything",
                secret_value="42",
                aws_credentials=aws_credentials
            )

        example_update_secret()
        ```

    """
    update_secret_kwargs: Dict[str, Union[str, bytes]] = dict(SecretId=secret_name)
    if description is not None:
        update_secret_kwargs["Description"] = description
    if isinstance(secret_value, bytes):
        update_secret_kwargs["SecretBinary"] = secret_value
    elif isinstance(secret_value, str):
        update_secret_kwargs["SecretString"] = secret_value
    else:
        raise ValueError("Please provide a bytes or str value for secret_value")

    logger = get_run_logger()
    logger.info("Updating value for secret %s", secret_name)

    client = aws_credentials.get_boto3_session().client("secretsmanager")

    try:
        response = await run_sync_in_worker_thread(
            client.update_secret, **update_secret_kwargs
        )
        response.pop("ResponseMetadata", None)
        return response
    except ClientError:
        logger.exception("Unable to update secret %s", secret_name)
        raise


@task
async def create_secret(
    secret_name: str,
    secret_value: Union[str, bytes],
    aws_credentials: AwsCredentials,
    description: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, str]:
    """
    Creates a secret in AWS Secrets Manager.

    Args:
        secret_name: The name of the secret to create.
        secret_value: The value to store in the created secret.
        aws_credentials: Credentials to use for authentication with AWS.
        description: A description for the created secret.
        tags: A list of tags to attach to the secret. Each tag should be specified as a
            dictionary in the following format:
            ```python
            {
                "Key": str,
                "Value": str
            }
            ```

    Returns:
        A dict containing the secret ARN (Amazon Resource Name),
            name, and current version ID.
            ```python
            {
                "ARN": str,
                "Name": str,
                "VersionId": str
            }
            ```
    Example:
        Create a secret:

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.secrets_manager import create_secret

        @flow
        def example_create_secret():
            aws_credentials = AwsCredentials(
                aws_access_key_id="access_key_id",
                aws_secret_access_key="secret_access_key"
            )
            create_secret(
                secret_name="life_the_universe_and_everything",
                secret_value="42",
                aws_credentials=aws_credentials
            )

        example_create_secret()
        ```


    """
    create_secret_kwargs: Dict[str, Union[str, bytes, List[Dict[str, str]]]] = dict(
        Name=secret_name
    )
    if description is not None:
        create_secret_kwargs["Description"] = description
    if tags is not None:
        create_secret_kwargs["Tags"] = tags
    if isinstance(secret_value, bytes):
        create_secret_kwargs["SecretBinary"] = secret_value
    elif isinstance(secret_value, str):
        create_secret_kwargs["SecretString"] = secret_value
    else:
        raise ValueError("Please provide a bytes or str value for secret_value")

    logger = get_run_logger()
    logger.info("Creating secret named %s", secret_name)

    client = aws_credentials.get_boto3_session().client("secretsmanager")

    try:
        response = await run_sync_in_worker_thread(
            client.create_secret, **create_secret_kwargs
        )
        print(response.pop("ResponseMetadata", None))
        return response
    except ClientError:
        logger.exception("Unable to create secret %s", secret_name)
        raise


@task
async def delete_secret(
    secret_name: str,
    aws_credentials: AwsCredentials,
    recovery_window_in_days: int = 30,
    force_delete_without_recovery: bool = False,
) -> Dict[str, str]:
    """
    Deletes a secret from AWS Secrets Manager.

    Secrets can either be deleted immediately by setting `force_delete_without_recovery`
    equal to `True`. Otherwise, secrets will be marked for deletion and available for
    recovery for the number of days specified in `recovery_window_in_days`

    Args:
        secret_name: Name of the secret to be deleted.
        aws_credentials: Credentials to use for authentication with AWS.
        recovery_window_in_days: Number of days a secret should be recoverable for
            before permanent deletion. Minimum window is 7 days and maximum window
            is 30 days. If `force_delete_without_recovery` is set to `True`, this
            value will be ignored.
        force_delete_without_recovery: If `True`, the secret will be immediately
            deleted and will not be recoverable.

    Returns:
        A dict containing the secret ARN (Amazon Resource Name),
            name, and deletion date of the secret. DeletionDate is the date and
            time of the delete request plus the number of days in
            `recovery_window_in_days`.
            ```python
            {
                "ARN": str,
                "Name": str,
                "DeletionDate": datetime.datetime
            }
            ```

    Examples:
        Delete a secret immediately:

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.secrets_manager import delete_secret

        @flow
        def example_delete_secret_immediately():
            aws_credentials = AwsCredentials(
                aws_access_key_id="access_key_id",
                aws_secret_access_key="secret_access_key"
            )
            delete_secret(
                secret_name="life_the_universe_and_everything",
                aws_credentials=aws_credentials,
                force_delete_without_recovery: True
            )

        example_delete_secret_immediately()
        ```

        Delete a secret with a 90 day recovery window:

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.secrets_manager import delete_secret

        @flow
        def example_delete_secret_with_recovery_window():
            aws_credentials = AwsCredentials(
                aws_access_key_id="access_key_id",
                aws_secret_access_key="secret_access_key"
            )
            delete_secret(
                secret_name="life_the_universe_and_everything",
                aws_credentials=aws_credentials,
                recovery_window_in_days=90
            )

        example_delete_secret_with_recovery_window()
        ```


    """
    if not force_delete_without_recovery and not (7 <= recovery_window_in_days <= 30):
        raise ValueError("Recovery window must be between 7 and 30 days.")

    delete_secret_kwargs: Dict[str, Union[str, int, bool]] = dict(SecretId=secret_name)
    if force_delete_without_recovery:
        delete_secret_kwargs[
            "ForceDeleteWithoutRecovery"
        ] = force_delete_without_recovery
    else:
        delete_secret_kwargs["RecoveryWindowInDays"] = recovery_window_in_days

    logger = get_run_logger()
    logger.info("Deleting secret %s", secret_name)

    client = aws_credentials.get_boto3_session().client("secretsmanager")

    try:
        response = await run_sync_in_worker_thread(
            client.delete_secret, **delete_secret_kwargs
        )
        response.pop("ResponseMetadata", None)
        return response
    except ClientError:
        logger.exception("Unable to delete secret %s", secret_name)
        raise


class AwsSecret(SecretBlock):
    """
    Manages a secret in AWS's Secrets Manager.

    Attributes:
        aws_credentials: The credentials to use for authentication with AWS.
        secret_name: The name of the secret.
    """

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa
    _block_type_name = "AWS Secret"
    _documentation_url = "https://prefecthq.github.io/prefect-aws/secrets_manager/#prefect_aws.secrets_manager.AwsSecret"  # noqa

    aws_credentials: AwsCredentials
    secret_name: str = Field(default=..., description="The name of the secret.")

    @sync_compatible
    async def read_secret(
        self,
        version_id: str = None,
        version_stage: str = None,
        **read_kwargs: Dict[str, Any],
    ) -> bytes:
        """
        Reads the secret from the secret storage service.

        Args:
            version_id: The version of the secret to read. If not provided, the latest
                version will be read.
            version_stage: The version stage of the secret to read. If not provided,
                the latest version will be read.
            read_kwargs: Additional keyword arguments to pass to the
                `get_secret_value` method of the boto3 client.

        Returns:
            The secret data.

        Examples:
            Reads a secret.
            ```python
            secrets_manager = SecretsManager.load("MY_BLOCK")
            secrets_manager.read_secret()
            ```
        """
        client = self.aws_credentials.get_secrets_manager_client()
        if version_id is not None:
            read_kwargs["VersionId"] = version_id
        if version_stage is not None:
            read_kwargs["VersionStage"] = version_stage
        response = await run_sync_in_worker_thread(
            client.get_secret_value, SecretId=self.secret_name, **read_kwargs
        )
        if "SecretBinary" in response:
            secret = response["SecretBinary"]
        elif "SecretString" in response:
            secret = response["SecretString"]
        arn = response["ARN"]
        self.logger.info(f"The secret {arn!r} data was successfully read.")
        return secret

    @sync_compatible
    async def write_secret(
        self, secret_data: bytes, **put_or_create_secret_kwargs: Dict[str, Any]
    ) -> str:
        """
        Writes the secret to the secret storage service as a SecretBinary;
        if it doesn't exist, it will be created.

        Args:
            secret_data: The secret data to write.
            **put_or_create_secret_kwargs: Additional keyword arguments to pass to
                put_secret_value or create_secret method of the boto3 client.

        Returns:
            The path that the secret was written to.

        Examples:
            Write some secret data.
            ```python
            secrets_manager = SecretsManager.load("MY_BLOCK")
            secrets_manager.write_secret(b"my_secret_data")
            ```
        """
        client = self.aws_credentials.get_secrets_manager_client()
        try:
            response = await run_sync_in_worker_thread(
                client.put_secret_value,
                SecretId=self.secret_name,
                SecretBinary=secret_data,
                **put_or_create_secret_kwargs,
            )
        except client.exceptions.ResourceNotFoundException:
            self.logger.info(
                f"The secret {self.secret_name!r} does not exist yet, creating it now."
            )
            response = await run_sync_in_worker_thread(
                client.create_secret,
                Name=self.secret_name,
                SecretBinary=secret_data,
                **put_or_create_secret_kwargs,
            )
        arn = response["ARN"]
        self.logger.info(f"The secret data was written successfully to {arn!r}.")
        return arn

    @sync_compatible
    async def delete_secret(
        self,
        recovery_window_in_days: int = 30,
        force_delete_without_recovery: bool = False,
        **delete_kwargs: Dict[str, Any],
    ) -> str:
        """
        Deletes the secret from the secret storage service.

        Args:
            recovery_window_in_days: The number of days to wait before permanently
                deleting the secret. Must be between 7 and 30 days.
            force_delete_without_recovery: If True, the secret will be deleted
                immediately without a recovery window.
            **delete_kwargs: Additional keyword arguments to pass to the
                delete_secret method of the boto3 client.

        Returns:
            The path that the secret was deleted from.

        Examples:
            Deletes the secret with a recovery window of 15 days.
            ```python
            secrets_manager = SecretsManager.load("MY_BLOCK")
            secrets_manager.delete_secret(recovery_window_in_days=15)
            ```
        """
        if force_delete_without_recovery and recovery_window_in_days:
            raise ValueError(
                "Cannot specify recovery window and force delete without recovery."
            )
        elif not (7 <= recovery_window_in_days <= 30):
            raise ValueError(
                "Recovery window must be between 7 and 30 days, got "
                f"{recovery_window_in_days}."
            )

        client = self.aws_credentials.get_secrets_manager_client()
        response = await run_sync_in_worker_thread(
            client.delete_secret,
            SecretId=self.secret_name,
            RecoveryWindowInDays=recovery_window_in_days,
            ForceDeleteWithoutRecovery=force_delete_without_recovery,
            **delete_kwargs,
        )
        arn = response["ARN"]
        self.logger.info(f"The secret {arn} was deleted successfully.")
        return arn
