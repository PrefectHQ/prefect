# `prefect-gcp`

`prefect-gcp` helps you leverage the capabilities of Google Cloud Platform (GCP) in your workflows.
For example, you can run flow on Vertex AI or Cloud Run, read and write data to BigQuery and Cloud Storage, retrieve secrets with Secret Manager.

## Getting Started

### Prerequisites

- [Prefect installed](https://docs.prefect.io/latest/getting-started/installation/) in a virtual environment.
- An [GCP account](https://cloud.google.com/) and the necessary permissions to access desired services.

### Install prefect-gcp

<div class = "terminal">
```bash
pip install -U prefect-gcp
```
</div>

### Register newly installed blocks types

Register the block types in the prefect-gcp module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_gcp
```
</div>

## Authenticate using a credentials block

authenticate with a service account in order to use `prefect-gcp`.

 `prefect-gcp` is able to safely save and load the service account, so they can be reused across the collection! Simply follow the steps below.

1. Refer to the [GCP service account documentation](https://cloud.google.com/iam/docs/creating-managing-service-account-keys#creating) on how to create and download a service account key file.
2. Copy the JSON contents.
3. Create a short script, replacing the placeholders with your information.

```python
from prefect_gcp import GcpCredentials

# replace this PLACEHOLDER dict with your own service account info
service_account_info = {
  "type": "service_account",
  "project_id": "PROJECT_ID",
  "private_key_id": "KEY_ID",
  "private_key": "-----BEGIN PRIVATE KEY-----\nPRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "SERVICE_ACCOUNT_EMAIL",
  "client_id": "CLIENT_ID",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://accounts.google.com/o/oauth2/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/SERVICE_ACCOUNT_EMAIL"
}

GcpCredentials(
    service_account_info=service_account_info
).save("BLOCK-NAME-PLACEHOLDER")
```

!!! warning "`service_account_info` vs `service_account_file`"

    The advantage of using `service_account_info`, instead of `service_account_file`, is that it is accessible across containers.
    
    If `service_account_file` is used, the provided file path *must be available* in the container executing the flow.

## Run flows on Google Cloud Run or Vertex AI

Run flows on [AWS Elastic Container Service (ECS)](https://aws.amazon.com/ecs/) to dynamically scale your infrastructure.

See the [ECS guide](/ecs_guide/) for a walkthrough of using ECS in a hybrid work pool.

If you're using Prefect Cloud and your organization's security posture allows storing credentials in blocks, [ECS push work pools](https://docs.prefect.io/latest/guides/deployment/push-work-pools/#__tabbed_1_1) are a great option.
They provide all the benefits of ECS with a quick setup and no worker needed.

## Execute commands through Cloud Run Jobs directly within a Prefect flow

```python
from prefect import flow
from prefect_gcp import GcpCredentials
from prefect_gcp.cloud_run import CloudRunJob

@flow
def cloud_run_job_flow():
    cloud_run_job = CloudRunJob(
        image="us-docker.pkg.dev/cloudrun/container/job:latest",
        credentials=GcpCredentials.load("BLOCK-NAME-PLACEHOLDER"),
        region="us-central1",
        command=["echo", "Hello, Prefect!"],
    )
    return cloud_run_job.run()
```

### Using Prefect with Google Vertex AI

`prefect_gcp` can enable you to execute your Prefect flows remotely, on-demand using Google Vertex AI too!

Be sure to additionally [install](#installation) the AI Platform extra!

Setting up a Vertex AI job is extremely similar to setting up a Cloud Run Job, but replace `CloudRunJob` with the following snippet.

```python
from prefect_gcp import GcpCredentials, VertexAICustomTrainingJob, GcsBucket

gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")

vertex_ai_job = VertexAICustomTrainingJob(
    image="IMAGE-NAME-PLACEHOLDER",  # must be from GCR and have Python + Prefect
    credentials=gcp_credentials,
    region="us-central1",
)
vertex_ai_job.save("test-example")
```

!!! info "Cloud Run Job vs Vertex AI"

    With Vertex AI, you can allocate computational resources on-the-fly for your executions, much like Cloud Run.
    
    However, unlike Cloud Run, you have the flexibility to provision instances with higher CPU, GPU, TPU, and RAM capacities.

    Additionally, jobs can run for up to 7 days, which is significantly longer than the maximum duration allowed on Cloud Run.

### Using Prefect with Google BigQuery

Got big data in BigQuery? `prefect_gcp` allows you to steadily stream data from and write to Google BigQuery within your Prefect flows!

Be sure to [install](#installation) `prefect-gcp` with the BigQuery extra!

The provided code snippet shows how you can use `prefect_gcp` to create a new dataset in BigQuery, define a table, insert rows, and fetch data from the table.

```python
from prefect import flow
from prefect_gcp.bigquery import GcpCredentials, BigQueryWarehouse

@flow
def bigquery_flow():
    all_rows = []
    gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")

    client = gcp_credentials.get_bigquery_client()
    client.create_dataset("test_example", exists_ok=True)

    with BigQueryWarehouse(gcp_credentials=gcp_credentials) as warehouse:
        warehouse.execute(
            "CREATE TABLE IF NOT EXISTS test_example.customers (name STRING, address STRING);"
        )
        warehouse.execute_many(
            "INSERT INTO test_example.customers (name, address) VALUES (%(name)s, %(address)s);",
            seq_of_parameters=[
                {"name": "Marvin", "address": "Highway 42"},
                {"name": "Ford", "address": "Highway 42"},
                {"name": "Unknown", "address": "Highway 42"},
            ],
        )
        while True:
            # Repeated fetch* calls using the same operation will
            # skip re-executing and instead return the next set of results
            new_rows = warehouse.fetch_many("SELECT * FROM test_example.customers", size=2)
            if len(new_rows) == 0:
                break
            all_rows.extend(new_rows)
    return all_rows

bigquery_flow()
```

### Using Prefect with Google Cloud Storage

With `prefect_gcp`, you can have peace of mind that your Prefect flows have not only seamlessly uploaded and downloaded objects to Google Cloud Storage, but also have these actions logged.

Be sure to additionally [install](#installation) `prefect-gcp` with the Cloud Storage extra!

The provided code snippet shows how you can use `prefect_gcp` to upload a file to a Google Cloud Storage bucket and download the same file under a different file name.

```python
from pathlib import Path
from prefect import flow
from prefect_gcp import GcpCredentials, GcsBucket


@flow
def cloud_storage_flow():
    # create a dummy file to upload
    file_path = Path("test-example.txt")
    file_path.write_text("Hello, Prefect!")

    gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")
    gcs_bucket = GcsBucket(
        bucket="BUCKET-NAME-PLACEHOLDER",
        gcp_credentials=gcp_credentials
    )

    gcs_bucket_path = gcs_bucket.upload_from_path(file_path)
    downloaded_file_path = gcs_bucket.download_object_to_path(
        gcs_bucket_path, "downloaded-test-example.txt"
    )
    return downloaded_file_path.read_text()


cloud_storage_flow()
```

!!! info "Upload and download directories"

    `GcsBucket` supports uploading and downloading entire directories. To view examples, check out the [Examples Catalog](examples_catalog/#cloud-storage-module)!

### Using Prefect with Google Secret Manager

Do you already have secrets available on Google Secret Manager? There's no need to migrate them!

`prefect_gcp` allows you to read and write secrets with Google Secret Manager within your Prefect flows.

Be sure to [install](#installation) `prefect-gcp` with the Secret Manager extra!

The provided code snippet shows how you can use `prefect_gcp` to write a secret to the Secret Manager, read the secret data, delete the secret, and finally return the secret data.

```python
from prefect import flow
from prefect_gcp import GcpCredentials, GcpSecret


@flow
def secret_manager_flow():
    gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")
    gcp_secret = GcpSecret(secret_name="test-example", gcp_credentials=gcp_credentials)
    gcp_secret.write_secret(secret_data=b"Hello, Prefect!")
    secret_data = gcp_secret.read_secret()
    gcp_secret.delete_secret()
    return secret_data

secret_manager_flow()
```

### Accessing Google credentials or clients from GcpCredentials

In the case that `prefect-gcp` is missing a feature, feel free to [submit an issue](#feedback).

In the meantime, you may want to access the underlying Google Cloud credentials or clients, which `prefect-gcp` exposes via the `GcpCredentials` block.

The provided code snippet shows how you can use `prefect_gcp` to instantiate a Google Cloud client, like `bigquery.Client`.

Note a `GcpCredentials` object is NOT a valid input to the underlying BigQuery client--use the `get_credentials_from_service_account` method to access and pass an actual `google.auth.Credentials` object.

```python
import google.cloud.bigquery
from prefect import flow
from prefect_gcp import GcpCredentials

@flow
def create_bigquery_client():
    gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")
    google_auth_credentials = gcp_credentials.get_credentials_from_service_account()
    bigquery_client = bigquery.Client(credentials=google_auth_credentials)
```

If you simply want to access the underlying client, `prefect-gcp` exposes a `get_client` method from `GcpCredentials`.

```python
from prefect import flow
from prefect_gcp import GcpCredentials

@flow
def create_bigquery_client():
    gcp_credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")
    bigquery_client = gcp_credentials.get_client("bigquery")
```

## Resources

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://docs.prefect.io/collections/usage/)!

### Installation

To use `prefect-gcp` and Cloud Run:

```bash
pip install prefect-gcp
```

To use Cloud Storage:

```bash
pip install "prefect-gcp[cloud_storage]"
```

To use BigQuery:

```bash
pip install "prefect-gcp[bigquery]"
```

To use Secret Manager:

```bash
pip install "prefect-gcp[secret_manager]"
```

To use Vertex AI:

```bash
pip install "prefect-gcp[aiplatform]"
```

A list of available blocks in `prefect-gcp` and their setup instructions can be found [here](https://prefecthq.github.io/prefect-gcp/blocks_catalog).

Requires an installation of Python 3.7+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Feedback

If you encounter any bugs while using `prefect-gcp`, feel free to open an issue in the [`prefect-gcp`](https://github.com/PrefectHQ/prefect-gcp) repository.

If you have any questions or issues while using `prefect-gcp`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

Feel free to star or watch [`prefect-gcp`](https://github.com/PrefectHQ/prefect-gcp) for updates too!
