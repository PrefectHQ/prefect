import json

from prefect.tasks.secrets.base import SecretBase
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


class AWSSecretsManager(SecretBase):
    """
    Task for retrieving secrets from an AWS Secrets Manager and returning it as a dictionary.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    For authentication, there are two options: you can set the `AWS_CREDENTIALS` Prefect Secret
    containing your AWS access keys which will be passed directly to the `boto3` client, or you
    can [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - secret (str, optional): the name of the secret to retrieve
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, secret: str = None, boto_kwargs: dict = None, **kwargs):
        self.secret = secret

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("secret")
    def run(self, secret: str = None, credentials: str = None) -> dict:
        """
        Task run method.

        Args:
            - secret (str): the name of the secret to retrieve
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.

        Returns:
            - dict: the contents of this secret, as a dictionary
        """

        if secret is None:
            raise ValueError("A secret name must be provided.")

        secrets_client = get_boto_client(
            "secretsmanager", credentials=credentials, **self.boto_kwargs
        )

        secret_string = secrets_client.get_secret_value(SecretId=secret)["SecretString"]

        secret_dict = json.loads(secret_string)

        return secret_dict
