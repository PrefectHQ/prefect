from typing import Union, Optional

from google.cloud import secretmanager

from prefect.tasks.secrets.base import SecretBase
from prefect.utilities.tasks import defaults_from_attrs


class GCPSecret(SecretBase):
    """
    Task for retrieving a secret from GCP Secrets Manager and returning it as a dictionary.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    For authentication, there are three options: you can set the `GCP_CREDENTIALS` Prefect Secret
    containing your GCP access keys, or [explicitly provide a credentials dictionary],
    or otherwise it will use [default Google client logic].

    [explicitly provide a credentials dictionary]
    https://googleapis.dev/python/google-api-core/latest/auth.html#explicit-credentials

    [default Google client logic]
    https://googleapis.dev/python/google-api-core/latest/auth.html

    Args:
        - project_id (Union[str, int], optional): the name of the project where the Secret is saved
        - secret_id (str, optional): the name of the secret to retrieve
        - version_id (Union[str, int], optional): the version number of the secret to use;
            defaults to 'latest'
        - credentials (dict, optional): dictionary containing GCP credentials
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        project_id: Union[str, int] = None,
        secret_id: str = None,
        version_id: Union[str, int] = "latest",
        credentials: Optional[dict] = None,
        **kwargs,
    ):
        self.project_id = project_id
        self.secret_id = secret_id
        self.version_id = version_id
        self.credentials = credentials
        super().__init__(**kwargs)

    @defaults_from_attrs("project_id", "secret_id", "version_id", "credentials")
    def run(
        self,
        project_id: Union[str, int] = None,
        secret_id: str = None,
        version_id: Union[str, int] = "latest",
        credentials: Optional[dict] = None,
    ) -> str:
        """
        Task run method.

        Args:
            - project_id (Union[str, int], optional): the name of the project where the Secret is saved
            - secret_id (str, optional): the name of the secret to retrieve
            - version_id (Union[str, int], optional): the version number of the secret to use;
                defaults to "latest"
            - credentials (dict, optional): your GCP credentials passed from an upstream Secret task.
                If not provided here default Google client logic will be used.

        Returns:
            - str: the contents of this secret
        """
        if project_id is None:
            raise ValueError("A GCP project ID must be provided.")
        if secret_id is None:
            raise ValueError("A GCP Secret Manager secret ID must be provided.")

        # Create the Secret Manager client.
        client = secretmanager.SecretManagerServiceClient(credentials=credentials)

        # Build the resource name of the secret version.
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

        # Access the secret version.
        response = client.access_secret_version(name=name)

        # Return the decoded payload.
        return response.payload.data.decode("UTF-8")
