# Storage Options

::: warning
Flows configured with environments are no longer supported. We recommend users transition to using [RunConfig](/orchestration/flow_config/run_configs.html) instead. See the [Flow Configuration](/orchestration/flow_config/overview.md) and [Upgrading Environments to RunConfig](/orchestration/faq/upgrade_environments.md) documentation for more information.

See [Storage](/orchestration/flow_config/storage.html) for current Flow definition storage capabilities.
:::

Prefect includes a variety of `Storage` options for saving flows.

As of Prefect version `0.9.0` every storage option except for `Docker` and `GitHub` will automatically have a result handler attached that will write results to the corresponding platform. For example, this means that if you register a flow with the Prefect API using the `S3` storage option then the flow's results will also be written to the same S3 bucket through the use of the [S3 Result](/api/latest/engine/results.html#s3result).

Version `0.12.0` introduced a new way to store flows using the various cloud storage options (S3, GCS, and Azure) and then, in turn, run them using agents that orchestrate containerized environments. For more information see [below](/orchestration/execution/storage_options.html#non-docker-storage-for-containerized-environments).

Version `0.12.5` introduced script-based storage for all storage options. For more information see the
[Using script based flow storage idiom](/core/idioms/script-based.html).

## Local

[Local Storage](/api/latest/storage.html#local) is the default `Storage` option for all flows. This stores the flow as bytes in the local filesystem, which means it can only be run by a [local agent](/orchestration/agents/local.html) running on the same machine.

```python
from prefect import Flow
from prefect.storage import Local

flow = Flow("local-flow", storage=Local())

flow.storage.build()
```

The flow is now available under `~/.prefect/flows/local-flow.prefect`.

::: tip Automatic Labels
Flows registered with this storage option will automatically be labeled with
the hostname of the machine from which it was registered. This prevents agents
not running on the same machine from attempting to run this flow.
:::

::: tip Flow Results
In more recent releases of Prefect Core, your flow will default to using a `LocalResult` for persisting any task results in the same file location.
:::

## Azure Blob Storage

[Azure Storage](/api/latest/storage.html#azure) is a storage option that uploads flows to an Azure Blob container.

```python
from prefect import Flow
from prefect.storage import Azure

flow = Flow("azure-flow", storage=Azure(container="<my-container>", connection_string_secret="<my-connection-string>"))

flow.storage.build()
```

The flow is now available in the container under `azure-flow/slugified-current-timestamp`.

::: tip Flow Results
In more recent releases of Core your flow will default to using a `AzureResult` for persisting any task results in the same Azure container.
:::

:::tip Azure Credentials
Azure Storage uses an Azure [connection string](https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string) for Azure authentication in aim to upload (build) or download flows, so make sure to provide a  valid connection string for your Azure account. A connection string can be set as a [secret](/orchestration/concepts/secrets.html#secrets) or an environment variable `AZURE_STORAGE_CONNECTION_STRING` in run configuration if it is not passed as `connection_string_secret`.
:::

## AWS S3

[S3 Storage](/api/latest/storage.html#s3) is a storage option that uploads flows to an AWS S3 bucket.

```python
from prefect import Flow
from prefect.storage import S3

flow = Flow("s3-flow", storage=S3(bucket="<my-bucket>"))

flow.storage.build()
```

The flow is now available in the bucket under `s3-flow/slugified-current-timestamp`.

::: tip Flow Results
In more recent releases of Core your flow will default to using a `S3Result` for persisting any task results in the same S3 bucket.
:::

:::tip AWS Credentials
S3 Storage uses AWS credentials the same way as [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) which means both upload (build) and download (local agent) times need to have proper AWS credential configuration.
:::

## Google Cloud Storage

[GCS Storage](/api/latest/storage.html#gcs) is a storage option that uploads flows to a Google Cloud Storage bucket.

```python
from prefect import Flow
from prefect.storage import GCS

flow = Flow("gcs-flow", storage=GCS(bucket="<my-bucket>"))

flow.storage.build()
```

The flow is now available in the bucket under `gcs-flow/slugified-current-timestamp`.

::: tip Flow Results
In more recent releases of Core your flow will default to using a `GCSResult` for persisting any task results in the same GCS location.
:::

:::tip Google Cloud Credentials
GCS Storage uses Google Cloud credentials the same way as the standard [google.cloud library](https://cloud.google.com/docs/authentication/production#auth-cloud-implicit-python) which means both upload (build) and download (local agent) times need to have the proper Google Application Credentials configuration.
:::

## GitHub

[GitHub Storage](/api/latest/storage.html#github) is a storage option that reads flows from a GitHub repository as .py files at runtime.

For a detailed look on how to use GitHub storage visit the [Using script based storage](/core/idioms/script-based.html) idiom.

:::tip GitHub Credentials
GitHub storage uses a [personal access token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line) for authenticating with repositories.
:::

## GitLab

[GitLab Storage](/api/latest/storage.html#github) is a storage option that reads flows from a GitHub repository as .py files at runtime.

Much of the GitHub example in the [script based storage](/core/idioms/script-based.html) documentation applies to GitLab as well.

:::tip GitLab Credentials
GitLab storage uses a [personal access token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) for authenticating with repositories.
:::

:::tip GitLab Server
GitLab server users can point the `host` argument to their personal GitLab instance.
:::

## Bitbucket

[Bitbucket Storage](/api/latest/storage.html#bitbucket) is a storage option that reads flows from a GitHub repository as .py files at runtime.

Much of the GitHub example in the [script based storage](/core/idioms/script-based.html) documentation applies to Bitbucket as well.

:::tip Bitbucket Credentials
Bitbucket storage uses a [personal access token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html) for authenticating with repositories.
:::

:::tip Bitbucket Server
Bitbucket server users can point the `host` argument to their personal or organization Bitbucket instance.
:::

:::tip Bitbucket Projects
Unlike GitHub or GitLab, Bitbucket organizes repositories in Projects and each repo must be associated with a Project. Bitbucket storage requires a `project` argument pointing to the correct project name.
:::

## CodeCommit

[CodeCommit Storage](/api/latest/storage.html#codecommit) is a storage option that reads flows from a GitHub repository as .py files at runtime.

:::tip AWS Credentials
CodeCommit uses AWS credentials the same way as [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) which means both upload (build) and download (local agent) times need to have proper AWS credential configuration.
:::

## Docker

[Docker Storage](/api/latest/storage.html#docker) is a storage option that puts flows inside of a Docker image and pushes them to a container registry. This method of Storage has deployment compatability with the [Docker Agent](/orchestration/agents/docker.html), [Kubernetes Agent](/orchestration/agents/kubernetes.html), and [Fargate Agent](/orchestration/agents/fargate.html).

```python
from prefect import Flow
from prefect.storage import Docker

flow = Flow("gcs-flow", storage=Docker(registry_url="<my-registry.io>", image_name="my_flow"))

flow.storage.build()
```

The flow is now available in the container registry under `my-registry.io/my_flow:slugified-current-timestamp`. Note that each type of container registry uses a different format for image naming (e.g. DockerHub vs GCR).

If you do not specify a `registry_url` for your Docker Storage then the image will not attempt to be pushed to a container registry and instead the image will live only on your local machine. This is useful when using the Docker Agent because it will not need to perform a pull of the image since it already exists locally.

:::tip Container Registry Credentials
Docker Storage uses the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/index.html) to build the image and push to a registry. Make sure you have the Docker daemon running locally and you are configured to push to your desired container registry. Additionally make sure whichever platform Agent deploys the container also has permissions to pull from that same registry.
:::

## Webhook

[Webhook Storage](/api/latest/storage.html#webhook) is a storage option that stores and retrieves flows with HTTP requests. This type of storage can be used with any type of agent, and is intended to be a flexible way to integrate Prefect with your existing ecosystem, including your own file storage services.

For example, the following code could be used to store flows in DropBox.

```python
from prefect import Flow
from prefect.storage import Webhook

flow = Flow(
    "dropbox-flow",
    storage=Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files/upload",
            "headers": {
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(
                    {
                        "path": "/Apps/prefect-test-app/dropbox-flow.flow",
                        "mode": "overwrite",
                        "autorename": False,
                        "strict_conflict": True,
                    }
                ),
                "Authorization": "Bearer ${DBOX_OAUTH2_TOKEN}"
            },
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files/download",
            "headers": {
                "Accept": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(
                    {"path": "/Apps/prefect-test-app/dropbox-flow.flow"}
                ),
                "Authorization": "Bearer ${DBOX_OAUTH2_TOKEN}"
            },
        },
        get_flow_request_http_method="POST",
    )
)

flow.storage.build()
```

Template strings in `${}` are used to reference sensitive information. Given `${SOME_TOKEN}`, this storage object will first look in environment variable `SOME_TOKEN` and then fall back to [Prefect secrets](/core/concepts/secrets.html) `SOME_TOKEN`. Because this resolution is at runtime, this storage option never has your sensitive information stored in it and that sensitive information is never sent to Prefect Cloud.

### Non-Docker Storage for Containerized Environments

Prefect allows for flows to be stored in cloud storage services and executed in containerized environments. This has the added benefit of rapidly deploying new versions of flows without having to rebuild images each time. To enable this functionality add an image name to the flow's Environment metadata.

```python
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.storage import S3

flow = Flow("example")

# set flow storage
flow.storage = S3(bucket="my-flows")

# set flow environment
flow.environment = LocalEnvironment(metadata={"image": "repo/name:tag"})
```

This example flow can now be run using an agent that orchestrates containerized environments. When the flow is run the image set in the environment's metadata will be used and inside that container the flow will be retrieved from the storage object (which is S3 in this example).

```bash
# starting a kubernetes agent that will pull flows stored in S3
prefect agent kubernetes start -l s3-flow-storage
```

::: tip Default Labels
The addition of these default labels can be disabled by passing `add_default_labels=False` to the flow's storage option. If this is set then the agents can ignore having to also set these labels. For more information on labels visit [the documentation](/orchestration/execution/overview.html#labels).
:::

#### Authentication for using Cloud Storage with Containerized Environments

One thing to keep in mind when using cloud storage options in conjunction with containerized environments is authentication. Since the flow is being retrieved from inside a container then that container must be authenticated to pull the flow from whichever cloud storage it has set. This means that at runtime the container needs to have the proper authentication.

Prefect has a couple [default secrets](/core/concepts/secrets.html#default-secrets) which could be used for off-the-shelf authentication. Using the above snippet as an example it is possible to create an `AWS_CREDENTIALS` Prefect secret that will automatically be used to pull the flow from S3 storage at runtime without having to configure authentication in the image directly.

```python
flow.storage = S3(bucket="my-flows", secrets=["AWS_CREDENTIALS"])

flow.environment = LocalEnvironment(metadata={"image": "prefecthq/prefect"})
```

::: warning Dependencies
It is important to make sure that the `image` set in the environment's metadata contains the dependencies required to use the storage option. For example, using `S3` storage requires Prefect's `aws` dependencies.

These are generally packaged with custom built images or optionally you could use the `prefecthq/prefect` image which contains all of Prefect's orchestration extras.
:::
