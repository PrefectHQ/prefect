import json
import uuid
from google.oauth2.service_account import Credentials
from google.cloud import storage
from google.cloud.exceptions import NotFound

from prefect import context
from prefect.client import Secret
from prefect.core import Task
from prefect.utilities.tasks import defaults_from_attrs


class GoogleCloudStorageTask(Task):
    def __init__(
        self,
        bucket,
        blob=None,
        project=None,
        create_bucket=False,
        credentials_secret=None,
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

    @defaults_from_attrs(
        ["bucket", "blob", "project", "create_bucket", "credentials_secret"]
    )
    def run(
        self,
        data,
        bucket=None,
        blob=None,
        project=None,
        create_bucket=False,
        credentials_secret=None,
    ):
        ## create client
        creds = json.loads(Secret(credentials_secret).get())
        project = project or credentials.project_id
        client = storage.Client(project=project, credentials=credentials)

        ## retrieve bucket
        try:
            bucket = client.get_bucket(bucket)
        except NotFound as exc:
            if create_bucket is True:
                bucket = client.create_bucket(bucket)
            else:
                raise exc

        ## identify blob name
        if blob is None:
            blob = "prefect-" + context.get("task_run_id", "no-id-" + str(uuid.uuid4()))

        ## pull encryption_key if requested
        if self.encryption_key_secret is not None:
            encryption_key = Secret(self.encryption_key_secret).get()
        else:
            encryption_key = None

        ## perform upload
        bucket.blob(blob, encryption_key=encryption_key).upload_from_string(data)
        return blob
