# Storage Options

Prefect natively has various different Storage options built in that can be used for saving Flows to different systems.

## Local

[Local Storage](/api/unreleased/environments/storage.html#local) is the default Storage options for all Flows. This stores the Flow as bytes in the local filesystem which means it can only be run by a [Local Agent](/cloud/agent/local.html) running on the same machine.

```python
from prefect import Flow
from prefect.environments.storage import Local

flow = Flow("local-flow", storage=Local())

storage.build()
```

The Flow is now available under `/.prefect/flows/local-flow.prefect`. **Note**: Flows registered with this Storage option will automatically be labeled with `hostname.local`.

## Azure Blob Storage

[Azure Storage](/api/unreleased/environments/storage.html#azure) is a Storage option which uploads Flows to an Azure Blob container. Currently Flows stored using this option can only be run by [Local Agents](/cloud/agent/local.html) as long as the machine running the Local Agent is configured to download from that Azure Blob container using a connection string.

```python
from prefect import Flow
from prefect.environments.storage import Azure

flow = Flow("azure-flow", storage=Azure(container="<my-container>", connection_string="<my-connection-string>"))

storage.build()
```

The Flow is now available in the container under `azure-flow/slugified-current-timestamp`. **Note**: Flows registered with this Storage option will automatically be labeled with `azure-flow-storage`.

:::tip Azure Credentials
Azure Storage uses an Azure [connection string](https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string) which means both upload (build) and download (Local Agent) times need to have a working Azure connection string. Azure Storage will also look in the environment variable `CONNECTION_STRING` if it is not passed to the class directly.
:::

## AWS S3

[S3 Storage](/api/unreleased/environments/storage.html#s3) is a Storage option which uploads Flows to an AWS S3 bucket. Currently Flows stored using this option can only be run by [Local Agents](/cloud/agent/local.html) as long as the machine running the Local Agent is configured to download from an S3 bucket.

```python
from prefect import Flow
from prefect.environments.storage import S3

flow = Flow("s3-flow", storage=S3(bucket="<my-bucket>"))

storage.build()
```

The Flow is now available in the bucket under `s3-flow/slugified-current-timestamp`. **Note**: Flows registered with this Storage option will automatically be labeled with `s3-flow-storage`.

:::tip AWS Credentials
S3 Storage uses AWS credentials the same way as [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) which means both upload (build) and download (Local Agent) times need to have proper AWS credential configuration.
:::

## Google Cloud Storage

[GCS Storage](/api/unreleased/environments/storage.html#gcs) is a Storage option which uploads Flows to a Google Cloud Storage bucket. Currently Flows stored using this option can only be run by [Local Agents](/cloud/agent/local.html) as long as the machine running the Local Agent is configured to download from a GCS bucket.

```python
from prefect import Flow
from prefect.environments.storage import GCS

flow = Flow("gcs-flow", storage=GCS(bucket="<my-bucket>"))

storage.build()
```

The Flow is now available in the bucket under `gcs-flow/slugified-current-timestamp`. **Note**: Flows registered with this Storage option will automatically be labeled with `gcs-flow-storage`.

:::tip Google Cloud Credentials
GCS Storage uses Google Cloud credentials the same way as the standard [google.cloud library](https://cloud.google.com/docs/authentication/production#auth-cloud-implicit-python) which means both upload (build) and download (Local Agent) times need to have the proper Google Application Credentials configuration.
:::

## Docker

[Docker Storage](/api/unreleased/environments/storage.html#docker) is a Storage option which puts Flows inside of a Docker image and pushes them to a container registry. This method of Storage has the largest deployment compatability with the [Docker Agent](/cloud/agent/docker.html), [Kubernetes Agent](/cloud/agent/kubernetes.html), and [Fargate Agent](/cloud/agent/fargate.html).

```python
from prefect import Flow
from prefect.environments.storage import Docker

flow = Flow("gcs-flow", storage=Docker(registry_url="<my-registry.io>", image_name="my_flow"))

storage.build()
```

The Flow is now available in the container registry under `my-registry.io/my_flow:slugified-current-timestamp`. Note that each type of container registry uses a different format for image naming (e.g. DockerHub vs GCR).

If you do not specify a `registry_url` for your Docker Storage then the image will not attempt to be pushed to a container registry and instead the image will live only on your local machine. This is useful when using the Docker Agent because it will not need to perform a pull of the image since it already exists locally.

:::tip Container Registry Credentials
Docker Storage uses the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/index.html) to build the image and push to a registry. Make sure you have the Docker daemon running locally and you are configured to push to your desired container registry. Additionally make sure whichever platform Agent deploys the container also has permissions to pull from that same registry.
:::
