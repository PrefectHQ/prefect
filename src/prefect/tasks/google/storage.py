import uuid

from google.oauth2.service_account import Credentials
from google.cloud import storage
from google.cloud.exceptions import NotFound

from prefect import context
from prefect.client import Secret
from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class GCSBaseTask(Task):
    def __init__(
        self,
        bucket,
        blob=None,
        project=None,
        credentials_secret=None,
        create_bucket=False,
        encryption_key_secret=None,
        **kwargs
    ):
        self.bucket = bucket
        self.blob = blob
        self.project = project
        self.create_bucket = create_bucket
        if credentials_secret is None:
            self.credentials_secret = "GOOGLE_APPLICATION_CREDENTIALS"
        else:
            self.credentials_secret = credentials_secret
        self.encryption_key_secret = encryption_key_secret
        super().__init__(**kwargs)

    def _load_client(self, project, credentials_secret):
        "Creates and returns a GCS Client instance"
        creds = Secret(credentials_secret).get()
        credentials = Credentials.from_service_account_info(creds)
        project = project or credentials.project_id
        client = storage.Client(project=project, credentials=credentials)
        return client

    def _retrieve_bucket(self, client, bucket, create_bucket):
        "Retrieves a bucket based on user settings"
        try:
            bucket = client.get_bucket(bucket)
        except NotFound as exc:
            if create_bucket is True:
                bucket = client.create_bucket(bucket)
            else:
                raise exc
        return bucket

    def _get_blob(self, bucket, blob, encryption_key_secret):
        "Retrieves blob based on user settings."
        if blob is None:
            blob = "prefect-" + context.get("task_run_id", "no-id-" + str(uuid.uuid4()))

        ## pull encryption_key if requested
        if encryption_key_secret is not None:
            encryption_key = Secret(encryption_key_secret).get()
        else:
            encryption_key = None

        return bucket.blob(blob, encryption_key=encryption_key)


class GCSDownload(GCSBaseTask):
    """
    Task template for downloading data from Google Cloud Storage as a string.

    Args:
        - bucket (str): default bucket name to download from; can be overwritten at runtime
        - blob (str, optional): default blob name to download; can be
            overwritten at runtime.  Required prior to running the task.
        - project (str, optional): default Google Cloud project to work within; can be overwritten at runtime.
            If not provided, will be inferred from your Google Cloud credentials
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON representation of your Google Cloud credentials; can be overwritten at runtime.
            Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
        - encryption_key_secret (str, optional): the name of the Prefect Secret
            storing an optional `encryption_key` to be used when downloading the Blob; can be overwritten at runtime
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor

    Note that the design of this task allows you to initialize a _template_ with default settings.  Each inidividual
    occurence of the task in a Flow can overwrite any of these default settings for custom use (for example, if you want to pull different
    credentials for a given Task, or specify the Blob name at runtime).
    """

    def __init__(
        self,
        bucket,
        blob=None,
        project=None,
        credentials_secret=None,
        encryption_key_secret=None,
        **kwargs
    ):
        super().__init__(
            bucket=bucket,
            blob=blob,
            project=project,
            credentials_secret=credentials_secret,
            encryption_key_secret=encryption_key_secret,
            **kwargs
        )

    @defaults_from_attrs(
        "blob", "bucket", "project", "credentials_secret", "encryption_key_secret"
    )
    def run(
        self,
        blob=None,
        bucket=None,
        project=None,
        credentials_secret=None,
        encryption_key_secret=None,
    ):
        """
        Run method for this Task.  Invoked by _calling_ this Task after initialization within a Flow context.

        Args:
            - blob (str, optional): blob name to download from; if not provided here or at initialization,
                a `ValueError` will be raised
            - bucket (str, optional): the bucket name to upload to; if not provided,
                will default to the one provided at initialization
            - project (str, optional): Google Cloud project to work within.
                If not provided here or at initialization, will be inferred from your Google Cloud credentials
            - credentials_secret (str, optional): the name of the Prefect Secret
                which stores a JSON represenation of your Google Cloud credentials; if not provided here or at initialization,
                `GOOGLE_APPLICATION_CREDENTIALS` will be used.
            - encryption_key_secret (str, optional): the name of the Prefect Secret
                storing an optional `encryption_key` to be used when uploading the Blob; if not provided here, will default to the
                one provided at initilization

        Raises:
            - google.cloud.exception.NotFound: if `create_bucket=False` and the bucket name is not found
            - ValueError: if `blob` name hasn't been provided

        Returns:
            - str: the data from the blob, as a string
        """
        ## create client
        client = self._load_client(project, credentials_secret)

        ## retrieve bucket
        bucket = self._retrieve_bucket(
            client=client, bucket=bucket, create_bucket=False
        )

        ## identify blob name
        gcs_blob = self._get_blob(bucket, blob, encryption_key_secret)
        data = gcs_blob.download_as_string()
        return data


class GCSUpload(GCSBaseTask):
    """
    Task template for uploading data to Google Cloud Storage.  Requires the data already be a string.

    Args:
        - bucket (str): default bucket name to upload to; can be overwritten at runtime
        - blob (str, optional): default blob name to upload to; can be overwritten at runtime,
            else a random string beginning with `prefect-` and containing the Task Run ID will be used
        - project (str, optional): default Google Cloud project to work within; can be overwritten at runtime.
            If not provided, will be inferred from your Google Cloud credentials
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON represenation of your Google Cloud credentials; can be overwritten at runtime.
            Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
        - create_bucket (bool, optional): boolean specifying whether to create the bucket if it does not exist,
            otherwise an Exception is raised; can be overwritten at runtime. Defaults to `False`.
        - encryption_key_secret (str, optional): the name of the Prefect Secret
            storing an optional `encryption_key` to be used when uploading the Blob; can be overwritten at runtime
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor

    Note that the design of this task allows you to initialize a _template_ with default settings.  Each inidividual
    occurence of the task in a Flow can overwrite any of these default settings for custom use (for example, if you want to pull different
    credentials for a given Task, or specify the Blob name at runtime).
    """

    def __init__(
        self,
        bucket,
        blob=None,
        project=None,
        credentials_secret=None,
        create_bucket=False,
        encryption_key_secret=None,
        **kwargs
    ):
        super().__init__(
            bucket=bucket,
            blob=blob,
            project=project,
            credentials_secret=credentials_secret,
            create_bucket=create_bucket,
            encryption_key_secret=encryption_key_secret,
            **kwargs
        )

    @defaults_from_attrs(
        "bucket",
        "blob",
        "project",
        "create_bucket",
        "credentials_secret",
        "encryption_key_secret",
    )
    def run(
        self,
        data,
        bucket=None,
        blob=None,
        project=None,
        credentials_secret=None,
        create_bucket=False,
        encryption_key_secret=None,
    ):
        """
        Run method for this Task.  Invoked by _calling_ this Task after initialization within a Flow context.

        Args:
            - data (str): the data to upload; must already be represented as a string
            - bucket (str, optional): the bucket name to upload to; if not provided,
                will default to the one provided at initialization
            - blob (str, optional): blob name to upload to; if not provided here or at initialization,
                a string beginning with `prefect-` and containing the Task Run ID will be used
            - project (str, optional): Google Cloud project to work within.
                If not provided here or at initialization, will be inferred from your Google Cloud credentials
            - credentials_secret (str, optional): the name of the Prefect Secret
                which stores a JSON represenation of your Google Cloud credentials; if not provided here or at initialization,
                `GOOGLE_APPLICATION_CREDENTIALS` will be used.
            - create_bucket (bool, optional): boolean specifying whether to create the bucket if it does not exist,
                otherwise an Exception is raised; if not provided here, will default to the value provided at initialization.
                Defaults to `False`.
            - encryption_key_secret (str, optional): the name of the Prefect Secret
                storing an optional `encryption_key` to be used when uploading the Blob; if not provided here, will default to the
                one provided at initilization

        Raises:
            - google.cloud.exception.NotFound: if `create_bucket=False` and the bucket name is not found

        Returns:
            - str: the blob name that now stores the provided data
        """
        ## create client
        client = self._load_client(project, credentials_secret)

        ## retrieve bucket
        bucket = self._retrieve_bucket(
            client=client, bucket=bucket, create_bucket=create_bucket
        )

        ## identify blob name
        gcs_blob = self._get_blob(bucket, blob, encryption_key_secret)
        gcs_blob.upload_from_string(data)
        return gcs_blob.name
