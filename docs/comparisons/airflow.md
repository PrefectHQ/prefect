# Airflow

| Feature                                    | Prefect    | Airflow    | Notes                                                                                          |
| ------------------------------------------ | :--------: | :--------: | ---------------------------------------------------------------------------------------------- |
|                                            |
| **WORKFLOW DEFINITION**                    |
| Workflows as code                          | [x] &nbsp; | [x] &nbsp; |
| Functional API                             | [x] &nbsp; | [ ] &nbsp; |
| Parameterized workflows                    | [x] &nbsp; | [ ] &nbsp; |
| Dataflow                                   | [x] &nbsp; | [ ] &nbsp; |
| Automatic input caching                    | [x] &nbsp; | [ ] &nbsp; |
| Support for output caching / "time travel" | [x] &nbsp; | [ ] &nbsp; |
|                                            |
| **EXECUTION**                              |
| Scheduled workflows                        | [x] &nbsp; | [x] &nbsp; |
| Ad-hoc workflows                           | [x] &nbsp; | [x] &nbsp; | Airflow has limited support for off-schedule execution                                         |
| Streaming workflows                        | [ ] &nbsp; | [ ] &nbsp; | Prefect will support streaming (long-running / async) workflows in an upcoming release         |
| Pause/resume workflows during execution    | [x] &nbsp; | [ ] &nbsp; |
| Event-driven scheduler                     | [x] &nbsp; | [ ] &nbsp; |
| Real-time execution                        | [x] &nbsp; | [ ] &nbsp; |
| Distributed execution                      | [x] &nbsp; | [x] &nbsp; | Prefect natively supports Dask clusters; Airflow supports distributed execution through Celery |
|                                            |
| **INTERACTION**                            |
| REST API                                   | [ ] &nbsp; | [x] &nbsp; | Airflow's limited REST API is in development                                                   |
| GraphQL API                                | [x] &nbsp; | [ ] &nbsp; |
|                                            |
| **DEPLOYMENT**                             |
| Workflow versioning and migration          | [x] &nbsp; | [ ] &nbsp; |
| Workflows as containers                    | [x] &nbsp; | [ ] &nbsp; |
| Configurable permissions                   | [x] &nbsp; | [x] &nbsp; | Airflow recently adopted RBAC                                                                  |
|                                            |
| **DEVELOPMENT**                            |
| Unit tests                                 | [x] &nbsp; | [x] &nbsp; | Prefect has 85% coverage; Airflow has 78% coverage |
| Local testing                              | [x] &nbsp; | [ ] &nbsp; | Prefect flows can be tested locally without any additional infrastructure                      |



## ETL Comparison

One of the most common use cases for a data engineering tool is designing an ETL pipeline.

### Prefect
Prefect makes this easy with native support for dataflow between tasks.
```python
from prefect import task, Flow

@task
def extract():
    """Produces a list of data"""
    return [1, 2, 3]

@task
def transform(x):
    """Transforms a list of data by multiplying it by 10"""
    return [i * 10 for i in x]

@task
def load(y):
    """Prints data to demonstrate it was received."""
    print("Here's your data: {}".format(y))

with Flow('ETL') as flow:
    e = extract()
    t = transform(e)
    l = load(t)
```


### Airflow
Airflow must fall back on XComs, a way to serialize small data to the Airflow database. This Airflow pipeline would fail with objects of any practical size.

<div class=comp-code>

```python
import datetime
import airflow
from airflow.operators import BaseOperator


class ExtractOperator(BaseOperator):
    """Produces a list of data"""
    def execute(self, context):
        data = [1, 2, 3]
        self.xcom_push(data)


class TransformOperator(BaseOperator):
    def __init__(self, extract_task_id, **kwargs):
        """
        Transforms a list of data by multiplying it by 10.

        Data must be pushed to an XCom by a task matching the provided
        `extract_task_id`.
        """
        self.extract_task_id = extract_task_id
        super().__init__(**kwargs)

    def execute(self, context):
        extracted_data = self.xcom_pull(task_id=self.extract_task_id)
        transformed_data = [i * 10 for i in extracted_data]
        self.xcom_push(transformed_data)


class LoadOperator(BaseOperator):
    def __init__(self, transform_task_id, **kwargs):
        """
        Prints data to demonstrate it was received.

        Data must be pushed to an XCom by a task matching the provided
        `transform_task_id`.
        """
        self.transform_task_id = transform_task_id
        super().__init__(**kwargs)

    def execute(self, context):
        transformed_data = self.xcom_pull(task_id=self.extract_task_id)
        print("Here's your data: {}".format(transformed_data))


dag = airflow.DAG(dag_id="ETL")

e = ExtractOperator(
    task_id="extract_operator", dag=dag, start_date=datetime.datetime(2018, 8, 1)
)
t = TransformOperator(
    task_id="transform_operator",
    extract_task_id="extract_operator",
    dag=dag,
    start_date=datetime.datetime(2018, 8, 1),
)
l = LoadOperator(
    task_id="load_operator",
    transform_task_id="transform_operator",
    dag=dag,
    start_date=datetime.datetime(2018, 8, 1),
)

e.set_downstream(t)
t.set_downstream(l)
```
</div>

## File Transfer comparison

This is a real example of a data pipeline that moves a file from Dropbox to Google Cloud Storage, then copies the file to a GCS archive.

### Prefect
The Prefect version is concise and looks like Python code, because Prefect allows each task to represent a discrete function. In this case, the library only requires a task that loads data from Dropbox; a task that loads data from Google Cloud Storage; and a task that saves data to Google Cloud Storage.

```python
from prefect import Task, Flow
import dropbox
from google.cloud import storage as gcs


class LoadFromDropbox(Task):
    """Loads data from a Dropbox path"""
    def __init__(self, api_key, **kwargs):
        self.api_key = api_key
        super().__init__(**kwargs)

    def run(self, path):
        response = dropbox.Dropbox(self.api_key).files_download(path)[1]
        return response.content


class LoadFromGCS(Task):
    """Loads data from a GCS path"""
    def __init__(self, service_account_key, **kwargs):
        self.service_account_key = service_account_key
        super().__init__(**kwargs)

    def run(self, bucket, path):
        client = gcs.Client(credentials=self.service_account_key)
        return client.get_bucket(bucket).get_blob(path)


class SaveToGCS(Task):
    """Writes data to a GCS path"""
    def __init__(self, service_account_key, **kwargs):
        self.service_account_key = service_account_key
        super().__init__(**kwargs)

    def run(self, data, bucket, path):
        client = gcs.Client(credentials=self.service_account_key)
        client.get_bucket(bucket).blob(path).upload_from_string(data)


with Flow("Transfer Example") as flow:
    get_from_dbx = LoadFromDropbox(api_key=DROPBOX_API_KEY)
    load_from_gcs = LoadFromGCS(service_account_key=GOOGLE_SERVICE_ACCOUNT_KEY)
    save_to_gcs = SaveToGCS(service_account_key=GOOGLE_SERVICE_ACCOUNT_KEY)

    dropbox_data = get_from_dbx("/files/file.txt")
    save_to_gcs(data=dropbox_data, bucket=GCS_BUCKET, path="current/file.txt")

    gcs_file = load_from_gcs(bucket=GCS_BUCKET, path="current/file.txt"))
    save_to_gcs(data=gcs_file, bucket=GCS_BUCKET, path="archive/2018/file.txt")

```
### Airflow
The Airflow version is extremely cumbersome. Because Airflow can not pass data between tasks, each task must perform an entire ETL cycle. As a result, internal Airflow libraries are full of operators representing every possible combination of data handoffs: `A_to_B_Operator`; `B_to_C_Operator`; `B_to_A_Operator`; `A_to_C_Operator`; `C_to_A_Operator`; etc.

This particular pipeline relies on a `DropboxToGoogleCloudStorage` operator, followed by a `GoogleCloudStorageToGoogleCloudStorage` operator.

*(This is actual sanitized Airflow code from one of Prefect's early partners)*

<div class=comp-code>

```python
import datetime
import tempfile
import airflow
import dropbox
from airflow.contrib.hooks.gcs_hook import GoogleCloudStorageHook
from airflow.contrib.operators.file_to_gcs import FileToGoogleCloudStorageOperator
from airflow.hooks.base_hook import BaseHook
from airflow.models import BaseOperator
from airflow.utils import apply_defaults
from airflow.utils.decorators import apply_defaults


class DropboxHook(BaseHook):
    """
    A hook for downloading files from Dropbox
    """

    def __init__(self, dbx_conn_id=None):
        self.dbx_conn_id = dbx_conn_id
        self.dbx_conn = self.get_conn()

    def get_conn(self):
        conn = self.get_connection(self.dbx_conn_id)
        return dropbox.Dropbox(conn.password)

    def download(self, dropbox_path, local_path=None):
        conn = self.get_conn()
        if local_path is not None:
            conn.files_download_to_file(local_path, dropbox_path)
        else:
            conn.files_download(dropbox_path)


class DropboxToGCSOperator(FileToGoogleCloudStorageOperator):
    """
    Uploads a file from Dropbox to Google Cloud Storage by reusing the
    FileToGoogleCloudStorageOperator but first downloading the file from
    Dropbox.
    """

    @apply_defaults
    def __init__(
        self,
        src,
        dst,
        bucket,
        dropbox_conn_id="dropbox_default",
        google_cloud_storage_conn_id="google_cloud_storage_default",
        *args,
        **kwargs
    ):
        """
        :param src: Path to the local file
        :type src: string
        :param dst: Destination path within the specified bucket
        :type dst: string
        :param bucket: The bucket to upload to
        :type bucket: string
        :param google_cloud_storage_conn_id: The Airflow connection ID to upload with
        :type google_cloud_storage_conn_id: string
        :param mime_type: The mime-type string
        :type mime_type: string
        :param delegate_to: The account to impersonate, if any
        :type delegate_to: string
        """
        super().__init__(
            src=src,
            dst=dst,
            bucket=bucket,
            google_cloud_storage_conn_id=google_cloud_storage_conn_id,
            *args,
            **kwargs
        )
        self.dropbox_conn_id = dropbox_conn_id

    def execute(self, context):
        original_src = self.src

        try:
            with tempfile.NamedTemporaryFile() as tmp:

                dropbox_hook = DropboxHook(dbx_conn_id=self.dropbox_conn_id)

                # download the dropbox file to a temporary location
                dropbox_hook.download(dropbox_path=self.src, local_path=tmp.name)

                # overwrite self.src with the new, local version of the file
                self.src = tmp.name

                # "rewind" the file and call the FileToGCS execute() method
                tmp.seek(0)
                super().execute(context)

        except Exception:
            raise
        finally:
            self.src = original_src


class GoogleCloudStorageToGoogleCloudStorageOperator(BaseOperator):
    """
    Copies an object from a bucket to another, with renaming if requested.

    :param source_bucket: The source Google cloud storage bucket where the object is.
    :type source_bucket: string
    :param source_object: The source name of the object to copy in the Google cloud
        storage bucket.
    :type source_object: string
    :param destination_bucket: The destination Google cloud storage bucket where the object should be.
    :type destination_bucket: string
    :param destination_object: The destination name of the object in the destination Google cloud
        storage bucket.
    :type destination_object: string
    :param google_cloud_storage_conn_id: The connection ID to use when
        connecting to Google cloud storage.
    :type google_cloud_storage_conn_id: string
    :param delegate_to: The account to impersonate, if any.
        For this to work, the service account making the request must have domain-wide delegation enabled.
    :type delegate_to: string
    """

    template_fields = (
        "source_bucket",
        "source_object",
        "destination_bucket",
        "destination_object",
    )
    ui_color = "#f0eee4"

    @apply_defaults
    def __init__(
        self,
        source_bucket,
        source_object,
        destination_bucket=None,
        destination_object=None,
        google_cloud_storage_conn_id="google_cloud_storage_default",
        delegate_to=None,
        *args,
        **kwargs
    ):
        super(GoogleCloudStorageToGoogleCloudStorageOperator, self).__init__(
            *args, **kwargs
        )
        self.source_bucket = source_bucket
        self.source_object = source_object
        self.destination_bucket = destination_bucket
        self.destination_object = destination_object
        self.google_cloud_storage_conn_id = google_cloud_storage_conn_id
        self.delegate_to = delegate_to

    def execute(self, context):
        hook = GoogleCloudStorageHook(
            google_cloud_storage_conn_id=self.google_cloud_storage_conn_id,
            delegate_to=self.delegate_to,
        )
        hook.copy(
            self.source_bucket,
            self.source_object,
            self.destination_bucket,
            self.destination_object,
        )


dbx_file = "/files/file.txt"
gcs_current = "current/file.txt"
gcs_archive = "archive/2018/file.txt"
dag = airflow.DAG(dag_id="transfer_example", start_date=datetime.datetime(2018, 9, 1))
dropbox_to_gcs = DropboxToGCSOperator(
    dropbox_conn_id=DROPBOX_CONN_ID,
    google_cloud_storage_conn_id=GCP_CONN_ID,
    src="/files/file.txt",
    bucket=GCS_BUCKET,
    dst="current/file.txt",
    dag=dag,
    task_id="move_data_from_dropbox_to_google_cloud_storage",
)
gcs_to_gcs = GoogleCloudStorageToGoogleCloudStorageOperator(
    google_cloud_storage_conn_id=GCP_CONN_ID,
    source_bucket=GCS_BUCKET,
    source_object="current/file.txt",
    destination_bucket=GCS_BUCKET,
    destination_object="archive/2018/file.txt",
    dag=dag,
    task_id="move_data_from_google_cloud_storage_current_to_google_cloud_storage_archive",
)
dropbox_to_gcs.set_downstream(gcs_to_gcs)
```
</div>
