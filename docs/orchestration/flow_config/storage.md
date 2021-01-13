# Storage

`Storage` objects define where a Flow should be stored. Examples include things
like `Local` storage (which uses the local filesystem) or `S3` (which stores
flows remotely on AWS S3). Flows themselves are never stored directly in
Prefect's backend; only a reference to the storage location is persisted. This
helps keep your flow's code secure, as the Prefect servers never have direct
access.

To configure a Flow's storage, you can either specify the `storage` as part of
the `Flow` constructor, or set it as an attribute later before calling
`flow.register`. For example, to configure a flow to use `Local` storage:

```python
from prefect import Flow
from prefect.storage import Local

# Set storage as part of the constructor
with Flow("example", storage=Local()) as flow:
    ...

# OR set storage as an attribute later
with Flow("example") as flow:
    ...

flow.storage = Local()
```

Prefect has a number of different `Storage` implementations - we'll briefly
cover each below. See [the API documentation](/api/latest/storage.md) for more
information.

## Local

[Local Storage](/api/latest/storage.md#local) is the default
`Storage` option for all flows. Flows using local storage are stored as files
in the local filesystem. This means they can only be run by a [local
agent](/orchestration/agents/local.md) running on the same machine.

```python
from prefect import Flow
from prefect.storage import Local

flow = Flow("local-flow", storage=Local())
```

After registration, the flow will be stored at
`~/.prefect/flows/<slugified-flow-name>/<slugified-current-timestamp>`.

:::tip Automatic Labels
Flows registered with this storage option will automatically be labeled with
the hostname of the machine from which it was registered; this prevents agents
not running on the same machine from attempting to run this flow.
:::

:::tip Flow Results
Flows configured with `Local` storage also default to using a `LocalResult` for
persisting any task results in the same filesystem.
:::

## AWS S3

[S3 Storage](/api/latest/storage.md#s3) is a storage option that
uploads flows to an AWS S3 bucket.

```python
from prefect import Flow
from prefect.storage import S3

flow = Flow("s3-flow", storage=S3(bucket="<my-bucket>"))
```

After registration, the flow will be stored in the specified bucket under
`<slugified-flow-name>/<slugified-current-timestamp>`.

:::tip Flow Results
Flows configured with `S3` storage also default to using a `S3Result` for
persisting any task results in the same S3 bucket.
:::

:::tip AWS Credentials
S3 Storage uses AWS credentials the same way as
[boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
which means both upload (build) and download (local agent) times need to have
proper AWS credential configuration.
:::

## Azure Blob Storage

[Azure Storage](/api/latest/storage.md#azure) is a storage
option that uploads flows to an Azure Blob container.

```python
from prefect import Flow
from prefect.storage import Azure

flow = Flow(
    "azure-flow",
    storage=Azure(
        container="<my-container>",
        connection_string="<my-connection-string>"
    )
)
```

After registration, the flow will be stored in the container under
`<slugified-flow-name>/<slugified-current-timestamp>`.

:::tip Flow Results
Flows configured with `Azure` storage also default to using an `AzureResult` for
persisting any task results to the same container in Azure Blob storage.
:::

:::tip Azure Credentials
Azure Storage uses an Azure [connection
string](https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string)
which means both upload (build) and download (local agent) times need to have a
working Azure connection string. Azure Storage will also look in the
environment variable `AZURE_STORAGE_CONNECTION_STRING` if it is not passed to
the class directly.
:::

## Google Cloud Storage

[GCS Storage](/api/latest/storage.md#gcs) is a storage option
that uploads flows to a Google Cloud Storage bucket.

```python
from prefect import Flow
from prefect.storage import GCS

flow = Flow("gcs-flow", storage=GCS(bucket="<my-bucket>"))
```

After registration the flow will be stored in the specified bucket under
`<slugified-flow-name>/<slugified-current-timestamp>`.

:::tip Flow Results
Flows configured with `GCS` storage also default to using a `GCSResult` for
persisting any task results in the same GCS location.
:::

:::tip Google Cloud Credentials
GCS Storage uses Google Cloud credentials the same way as the standard
[google.cloud
library](https://cloud.google.com/docs/authentication/production#auth-cloud-implicit-python)
which means both upload (build) and download (local agent) times need to have
the proper Google Application Credentials configuration.
:::

## GitHub

[GitHub Storage](/api/latest/storage.md#github) is a storage
option for referencing flows stored in a GitHub repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import GitHub

flow = Flow(
    "github-flow",
    GitHub(
        repo="org/repo",                 # name of repo
        path="flows/my_flow.py",         # location of flow file in repo
        secrets=["GITHUB_ACCESS_TOKEN"]  # name of personal access token secret
    )
)
```

For a detailed look on how to use GitHub storage visit the [Using file based
storage](/core/idioms/file-based.md) idiom.

:::tip GitHub Credentials
GitHub storage uses a [personal access
token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line)
for authenticating with repositories.
:::

## GitLab

[GitLab Storage](/api/latest/storage.md#gitlab) is a storage
option for referencing flows stored in a GitLab repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import GitLab

flow = Flow(
    "gitlab-flow",
    GitLab(
        repo="org/repo",                 # name of repo
        path="flows/my_flow.py",         # location of flow file in repo
        secrets=["GITLAB_ACCESS_TOKEN"]  # name of personal access token secret
    )
)
```

Much of the GitHub example in the [file based
storage](/core/idioms/file-based.md) documentation applies to GitLab as well.

:::tip GitLab Credentials
GitLab storage uses a [personal access
token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) for
authenticating with repositories.
:::

:::tip GitLab Server
GitLab server users can point the `host` argument to their personal GitLab
instance.
:::

## Bitbucket

[Bitbucket Storage](/api/latest/storage.html#github) is a
storage option that uploads flows to a Bitbucket repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import Bitbucket

flow = Flow(
    "bitbucket-flow",
    Bitbucket(
        project="project",                  # name of project
        repo="project.repo",                # name of repo in project
        path="flows/my_flow.py",            # location of flow file in repo
        secrets=["BITBUCKET_ACCESS_TOKEN"]  # name of personal access token secret
    )
)
```

Much of the GitHub example in the [file based
storage](/core/idioms/file-based.html) documentation applies to Bitbucket as well.

:::tip Bitbucket Credentials
Bitbucket storage uses a [personal access
token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)
for authenticating with repositories.
:::

:::tip Bitbucket Projects
Unlike GitHub or GitLab, Bitbucket organizes repositories in Projects and each repo
must be associated with a Project. Bitbucket storage requires a `project` argument
pointing to the correct project name.
:::

## CodeCommit

[CodeCommit Storage](/api/latest/storage.html#codecommit) is a
storage option that uploads flows to a CodeCommit repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import GitLab

flow = Flow(
    "codecommit-flow",
    CodeCommit(
        repo="org/repo",                 # name of repo
        path="flows/my_flow.py",         # location of flow file in repo
        commit='dev',                    # branch, tag or commit id
    )
)
```

:::tip AWS Credentials
S3 Storage uses AWS credentials the same way as
[boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
which means both upload (build) and download (local agent) times need to
have proper AWS credential configuration.
:::

## Docker

[Docker Storage](/api/latest/storage.md#docker) is a storage
option that puts flows inside of a Docker image and pushes them to a container
registry. This method of Storage has deployment compatability with the [Docker
Agent](/orchestration/agents/docker.md), [Kubernetes
Agent](/orchestration/agents/kubernetes.md), and [Fargate
Agent](/orchestration/agents/fargate.md).

```python
from prefect import Flow
from prefect.storage import Docker

flow = Flow(
    "docker-flow",
    storage=Docker(registry_url="<my-registry.io>", image_name="my_flow")
)
```

After registration, the flow's image will be stored in the container registry
under `my-registry.io/<slugified-flow-name>:<slugified-current-timestamp>`. Note that each
type of container registry uses a different format for image naming (e.g.
DockerHub vs GCR).

If you do not specify a `registry_url` for your Docker Storage then the image
will not attempt to be pushed to a container registry and instead the image
will live only on your local machine. This is useful when using the Docker
Agent because it will not need to perform a pull of the image since it already
exists locally.

:::tip Container Registry Credentials
Docker Storage uses the [Docker SDK for
Python](https://docker-py.readthedocs.io/en/stable/index.html) to build the
image and push to a registry. Make sure you have the Docker daemon running
locally and you are configured to push to your desired container registry.
Additionally make sure whichever platform Agent deploys the container also has
permissions to pull from that same registry.
:::

## Webhook

[Webhook Storage](/api/latest/storage.md#webhook) is a storage
option that stores and retrieves flows with HTTP requests. This type of storage
can be used with any type of agent, and is intended to be a flexible way to
integrate Prefect with your existing ecosystem, including your own file storage
services.

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
```

Template strings in `${}` are used to reference sensitive information. Given
`${SOME_TOKEN}`, this storage object will first look in environment variable
`SOME_TOKEN` and then fall back to [Prefect
secrets](/core/concepts/secrets.md) `SOME_TOKEN`. Because this resolution is
at runtime, this storage option never has your sensitive information stored in
it and that sensitive information is never sent to Prefect Cloud.
