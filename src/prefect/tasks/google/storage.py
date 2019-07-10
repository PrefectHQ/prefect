import uuid

from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.oauth2.service_account import Credentials

from prefect import context
from prefect.client import Secret
from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class GCSBaseTask(Task):
    def __init__(
        self,
        bucket: str,
        blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        create_bucket: bool = False,
        encryption_key_secret: str = None,
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

    def _load_client(self, project: str, credentials_secret: str):
        "Creates and returns a GCS Client instance"
        creds = Secret(credentials_secret).get()
        credentials = Credentials.from_service_account_info(creds)
        project = project or credentials.project_id
        client = storage.Client(project=project, credentials=credentials)
        return client

    def _retrieve_bucket(self, client, bucket: str, create_bucket: bool):
        "Retrieves a bucket based on user settings"
        try:
            bucket = client.get_bucket(bucket)
        except NotFound as exc:
            if create_bucket is True:
                self.logger.debug("Bucket {} not found; creating...".format(bucket))
                bucket = client.create_bucket(bucket)
            else:
                raise exc
        return bucket

    def _get_blob(self, bucket: str, blob: str, encryption_key_secret: str):
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
        - bucket (str): default bucket name to download from
        - blob (str, optional): default blob name to download.
        - project (str, optional): default Google Cloud project to work within.
            If not provided, will be inferred from your Google Cloud credentials
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON representation of your Google Cloud credentials.
            Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
        - encryption_key_secret (str, optional): the name of the Prefect Secret
            storing an optional `encryption_key` to be used when downloading the Blob
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor

    Note that the design of this task allows you to initialize a _template_ with default settings.  Each inidividual
    occurence of the task in a Flow can overwrite any of these default settings for custom use (for example, if you want to pull different
    credentials for a given Task, or specify the Blob name at runtime).
    """

    def __init__(
        self,
        bucket: str,
        blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        encryption_key_secret: str = None,
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
        bucket: str = None,
        blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        encryption_key_secret: str = None,
    ) -> str:
        """
        Run method for this Task.  Invoked by _calling_ this Task after initialization
        within a Flow context.

        Note that some arguments are required for the task to run, and must be provided
        _either_ at initialization _or_ as arguments.

        Args:
            - bucket (str, optional): the bucket name to upload to
            - blob (str, optional): blob name to download from
            - project (str, optional): Google Cloud project to work within.
                If not provided here or at initialization, will be inferred from your Google Cloud credentials
            - credentials_secret (str, optional): the name of the Prefect Secret
                that stores a JSON represenation of your Google Cloud credentials
                `GOOGLE_APPLICATION_CREDENTIALS` will be used.
            - encryption_key_secret (str, optional): the name of the Prefect Secret
                storing an optional `encryption_key` to be used when uploading the Blob

        Returns:
            - str: the data from the blob, as a string

        Raises:
            - google.cloud.exception.NotFound: if `create_bucket=False` and the bucket
                name is not found
            - ValueError: if `blob` name hasn't been provided

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
    Task template for uploading data to Google Cloud Storage.  Requires the data already
    be a string.

    Args:
        - bucket (str): default bucket name to upload to
        - blob (str, optional): default blob name to upload to; otherwise a random string
            beginning with `prefect-` and containing the Task Run ID will be used
        - project (str, optional): default Google Cloud project to work within.
            If not provided, will be inferred from your Google Cloud credentials
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON represenation of your Google Cloud credentials.
            Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
        - create_bucket (bool, optional): boolean specifying whether to create the bucket if it does not exist,
            otherwise an Exception is raised. Defaults to `False`.
        - encryption_key_secret (str, optional): the name of the Prefect Secret
            storing an optional `encryption_key` to be used when uploading the Blob
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor

    Note that the design of this task allows you to initialize a _template_ with default
    settings.  Each inidividual occurence of the task in a Flow can overwrite any of
    these default settings for custom use (for example, if you want to pull different
    credentials for a given Task, or specify the Blob name at runtime).
    """

    def __init__(
        self,
        bucket: str,
        blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        create_bucket: bool = False,
        encryption_key_secret: str = None,
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
        data: str,
        bucket: str = None,
        blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        create_bucket: bool = False,
        encryption_key_secret: str = None,
    ) -> str:
        """
        Run method for this Task.  Invoked by _calling_ this Task after initialization
        within a Flow context.

        Note that some arguments are required for the task to run, and must be
        provided _either_ at initialization _or_ as arguments.

        Args:
            - data (str): the data to upload; must already be represented as a string
            - bucket (str, optional): the bucket name to upload to
            - blob (str, optional): blob name to upload to
                a string beginning with `prefect-` and containing the Task Run ID will be used
            - project (str, optional): Google Cloud project to work within. Can be inferred
                from credentials if not provided.
            - credentials_secret (str, optional): the name of the Prefect Secret
                which stores a JSON represenation of your Google Cloud credentials.
                Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
            - create_bucket (bool, optional): boolean specifying whether to create the bucket
                if it does not exist, otherwise an Exception is raised. Defaults to `False`.
            - encryption_key_secret (str, optional): the name of the Prefect Secret
                storing an optional `encryption_key` to be used when uploading the Blob.

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


class GCSCopy(Task):
    """
    Task template for copying data from one Google Cloud Storage bucket to another, without
    downloading it locally.

    Note that some arguments are required for the task to run, and must be
    provided _either_ at initialization _or_ as arguments.

    Args:
        - source_bucket (str, optional): default source bucket name.
        - source_blob (str, optional): default source blob name.
        - dest_bucket (str, optional): default destination bucket name.
        - dest_blob (str, optional): default destination blob name.
        - project (str, optional): default Google Cloud project to work within.
            If not provided, will be inferred from your Google Cloud credentials
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON representation of your Google Cloud credentials.
            Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor

    Note that the design of this task allows you to initialize a _template_ with default settings.  Each inidividual
    occurence of the task in a Flow can overwrite any of these default settings for custom use (for example, if you want to pull different
    credentials for a given Task, or specify the Blob name at runtime).
    """

    def __init__(
        self,
        source_bucket: str = None,
        source_blob: str = None,
        dest_bucket: str = None,
        dest_blob: str = None,
        project: str = None,
        credentials_secret: str = None,
        **kwargs
    ):
        self.source_bucket = source_bucket
        self.source_blob = source_blob
        self.dest_bucket = dest_bucket
        self.dest_blob = dest_blob
        self.project = project
        if credentials_secret is None:
            self.credentials_secret = "GOOGLE_APPLICATION_CREDENTIALS"
        else:
            self.credentials_secret = credentials_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source_bucket",
        "source_blob",
        "dest_bucket",
        "dest_blob",
        "project",
        "credentials_secret",
    )
    def run(
        self,
        source_bucket: str = None,
        source_blob: str = None,
        dest_bucket: str = None,
        dest_blob: str = None,
        project: str = None,
        credentials_secret: str = None,
    ) -> str:
        """
        Run method for this Task. Invoked by _calling_ this Task after initialization
        within a Flow context.

        Note that some arguments are required for the task to run, and must be
        provided _either_ at initialization _or_ as arguments.

        Args:
            - source_bucket (str, optional): default source bucket name.
            - source_blob (str, optional): default source blob name.
            - dest_bucket (str, optional): default destination bucket name.
            - dest_blob (str, optional): default destination blob name.
            - project (str, optional): default Google Cloud project to work within.
                If not provided, will be inferred from your Google Cloud credentials
            - credentials_secret (str, optional): the name of the Prefect Secret
                which stores a JSON representation of your Google Cloud credentials.
                Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.

        Returns:
            - str: the name of the destination blob

        Raises:
            - ValueError: if `source_bucket`, `source_blob`, `dest_bucket`, or `dest_blob`
                are missing or point at the same object.

        """
        if None in [source_bucket, source_blob, dest_bucket, dest_blob]:
            raise ValueError("Missing source or destination")
        elif (source_bucket, source_blob) == (dest_bucket, dest_blob):
            raise ValueError("Source and destination are identical.")

        ## create client
        creds = Secret(credentials_secret).get()
        credentials = Credentials.from_service_account_info(creds)
        project = project or credentials.project_id
        client = storage.Client(project=project, credentials=credentials)

        # get source bucket and blob
        source_bucket_obj = client.get_bucket(source_bucket)
        source_blob_obj = source_bucket_obj.blob(source_blob)
        # get dest bucket
        dest_bucket_obj = client.get_bucket(dest_bucket)
        # copy from source blob to dest bucket
        source_bucket_obj.copy_blob(
            blob=source_blob_obj, destination_bucket=dest_bucket_obj, new_name=dest_blob
        )

        return dest_blob
