# Storage Options

Prefect includes a variety of `Storage` options for saving flows.

As of Prefect version `0.9.0` every storage option except for `Docker` will automatically have a result handler attached that will write results to the corresponding platform. For example, this means that if you register a flow with the Prefect API using the `S3` storage option then the flow's results will also be written to the same S3 bucket through the use of the [S3 Result Handler](/api/latest/engine/result_handlers.html#s3resulthandler).

## Local

[Local Storage](/api/latest/environments/storage.html#local) is the default `Storage` option for all flows. This stores the flow as bytes in the local filesystem which means it can only be run by a [local agent](/orchestration/agents/local.html) running on the same machine.

```python
from prefect import Flow
from prefect.environments.storage import Local

flow = Flow("local-flow", storage=Local())

flow.storage.build()
```

The flow is now available under `~/.prefect/flows/local-flow.prefect`.

::: tip Sensible Defaults
Flows registered with this storage option will automatically be labeled with the hostname of the machine from which it was registered; this prevents agents not running on the same machine from attempting to run this flow.

Additionally, in more recent releases of Core your flow will default to using a `LocalResultHandler` for persisting any task results in the same file location.
:::

## Azure Blob Storage

[Azure Storage](/api/latest/environments/storage.html#azure) is a storage option that uploads flows to an Azure Blob container. Currently flows stored using this option can only be run by [local agents](/orchestration/agents/local.html) as long as the machine running the local agent is configured to download from that Azure Blob container using a connection string.

```python
from prefect import Flow
from prefect.environments.storage import Azure

flow = Flow("azure-flow", storage=Azure(container="<my-container>", connection_string="<my-connection-string>"))

flow.storage.build()
```

The flow is now available in the container under `azure-flow/slugified-current-timestamp`.

::: tip Sensible Defaults
Flows registered with this storage option will automatically be labeled with `"azure-flow-storage"`; this prevents agents not explicitly authenticated with your Azure deployment from attempting to run this flow.

Additionally, in more recent releases of Core your flow will default to using a `AzureResultHandler` for persisting any task results in the same Azure container.
:::

:::tip Azure Credentials
Azure Storage uses an Azure [connection string](https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string) which means both upload (build) and download (local agent) times need to have a working Azure connection string. Azure Storage will also look in the environment variable `AZURE_STORAGE_CONNECTION_STRING` if it is not passed to the class directly.
:::

## AWS S3

[S3 Storage](/api/latest/environments/storage.html#s3) is a storage option that uploads flows to an AWS S3 bucket. Currently flows stored using this option can only be run by [local agents](/orchestration/agents/local.html) as long as the machine running the local agent is configured to download from an S3 bucket.

```python
from prefect import Flow
from prefect.environments.storage import S3

flow = Flow("s3-flow", storage=S3(bucket="<my-bucket>"))

flow.storage.build()
```

The flow is now available in the bucket under `s3-flow/slugified-current-timestamp`.

::: tip Sensible Defaults
Flows registered with this storage option will automatically be labeled with `"s3-flow-storage"`; this helps prevent agents not explicitly authenticated with your AWS deployment from attempting to run this flow.

Additionally, in more recent releases of Core your flow will default to using a `S3ResultHandler` for persisting any task results in the same S3 bucket.
:::

:::tip AWS Credentials
S3 Storage uses AWS credentials the same way as [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) which means both upload (build) and download (local agent) times need to have proper AWS credential configuration.
:::

## Google Cloud Storage

[GCS Storage](/api/latest/environments/storage.html#gcs) is a storage option that uploads flows to a Google Cloud Storage bucket. Currently flows stored using this option can only be run by [local agents](/orchestration/agents/local.html) as long as the machine running the local agent is configured to download from a GCS bucket.

```python
from prefect import Flow
from prefect.environments.storage import GCS

flow = Flow("gcs-flow", storage=GCS(bucket="<my-bucket>"))

flow.storage.build()
```

The flow is now available in the bucket under `gcs-flow/slugified-current-timestamp`.

::: tip Sensible Defaults
Flows registered with this storage option will automatically be labeled with `"gcs-flow-storage"`; this helps prevents agents not explicitly authenticated with your GCS project from attempting to run this flow.

Additionally, in more recent releases of Core your flow will default to using a `GCSResultHandler` for persisting any task results in the same GCS location.
:::

:::tip Google Cloud Credentials
GCS Storage uses Google Cloud credentials the same way as the standard [google.cloud library](https://cloud.google.com/docs/authentication/production#auth-cloud-implicit-python) which means both upload (build) and download (local agent) times need to have the proper Google Application Credentials configuration.
:::

## Docker

[Docker Storage](/api/latest/environments/storage.html#docker) is a storage option that puts flows inside of a Docker image and pushes them to a container registry. This method of Storage has the largest deployment compatability with the [Docker Agent](/orchestration/agents/docker.html), [Kubernetes Agent](/orchestration/agents/kubernetes.html), and [Fargate Agent](/orchestration/agents/fargate.html).

```python
from prefect import Flow
from prefect.environments.storage import Docker

flow = Flow("gcs-flow", storage=Docker(registry_url="<my-registry.io>", image_name="my_flow"))

flow.storage.build()
```

The flow is now available in the container registry under `my-registry.io/my_flow:slugified-current-timestamp`. Note that each type of container registry uses a different format for image naming (e.g. DockerHub vs GCR).

If you do not specify a `registry_url` for your Docker Storage then the image will not attempt to be pushed to a container registry and instead the image will live only on your local machine. This is useful when using the Docker Agent because it will not need to perform a pull of the image since it already exists locally.

:::tip Container Registry Credentials
Docker Storage uses the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/index.html) to build the image and push to a registry. Make sure you have the Docker daemon running locally and you are configured to push to your desired container registry. Additionally make sure whichever platform Agent deploys the container also has permissions to pull from that same registry.
:::
