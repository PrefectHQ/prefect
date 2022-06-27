# Storage

`Storage` objects define where a Flow's definition is stored. Examples include
things like `Local` storage (which uses the local filesystem) or `S3` (which
stores flows remotely on AWS S3). Flows themselves are never stored directly in
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

## Pickle vs Script Based Storage

Prefect Storage classes support two ways of storing a flow's definition:

### Pickle based storage

Pickle based flow storage uses the `cloudpickle` library to "pickle"
(serialize) the `Flow` object. At runtime the flow is unpickled and can then be
executed.

This means that the flow's definition is effectively "frozen" at registration
time. Anything executed at the top-level of the script will only execute at
flow *registration* time, not at flow *execution* time.

```python
from prefect import Flow

# Top-level functionality (like this print statement) runs only at flow
# *registration* time, it will not run during each flow run. If you want
# something to run as part of a flow, you must write it as a task.
print("This print only runs at flow registration time")

with Flow("example") as flow:
    pass
```

### Script based storage

Script based flow storage uses the Python script that created the flow as the
flow definition. Each time the flow is run, the script will be run to recreate
the `Flow` object.

This has a few nice properties:

- Script based flows allow you to make small edits to the source of your flow
  without re-registration. Changing the flow's structure (e.g. adding new tasks
  or edges) or the flow's metadata (e.g. updating the run config) will require
  re-registration, but editing the definitions for individual tasks is fine.

- Pickle based flows are prone to breakage if the internals of Prefect or a
  dependent library changes (even if the public-facing API remains the same).
  Using a script based flow storage your flow is likely to work across a larger
  range of Prefect/Python/dependency versions.

The downside is you may have to do a bit more configuration to tell prefect
where your script is located (since it can't always be automatically inferred).

Some storage classes (such as `GitHub`, `Bitbucket`, and `GitLab`) only support
script-based flow storage. Other classes (including `Local`, `S3`, and `GCS`)
support both &mdash; pickle is used by default, but you can opt in to script-based
storage by passing `stored_as_script=True`. See the [script based storage
idiom](/core/idioms/script-based.html) for more information.

## Choosing a Storage Class

Prefect's storage mechanism is flexible, supporting many different backends and
deployment strategies. However, such flexibility can be daunting for both new
and experienced users. Below we provide a few general recommendations for
deciding what Storage mechanism is right for you.

- If you're deploying flows locally using a [local
  agent](/orchestration/agents/local.md), you likely want to use the default
  [Local](#local) storage class. It requires no external resources, and is
  quick to configure.

- If you store your flows in a code repository, you may want to use the
  corresponding storage class (such as [GitHub](#github), [Bitbucket](#bitbucket),
  or [GitLab](#gitlab)).  During a flow run, your flow source will be pulled
  from the repo (optionally from a specific commit/branch) before execution.

- If you're making use of cloud storage within your flows, you may want to
  store your flow source in the same location. Storage classes like
  [S3](#aws-s3), [GCS](#google-cloud-storage), and [Azure](#azure-blob-storage)
  make it possible to specify a single location for hosting both your flow
  source and results from that flow.

## Storage Types

Prefect has a number of different `Storage` implementations. We'll briefly
cover each below. See [the API documentation](/api/latest/storage.md) for more
information.

### Local

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

!!! tip Automatic Labels
    Flows registered with this storage option will automatically be labeled with
    the hostname of the machine from which it was registered; this prevents agents
    not running on the same machine from attempting to run this flow. This default
    prevents the common issue where an agent cannot find a flow that is stored on a
    different machine. You can override this behavior by passing `add_default_labels=False`
    to the object, but then you must make sure that the flow file is available on
    the local file system of other agents.
    ```python
    flow = Flow("local-flow", storage=Local(add_default_labels=False))
    ```
:::

!!! tip Flow Results
    Flows configured with `Local` storage also default to using a `LocalResult` for
    persisting any task results in the same filesystem.
:::

### Module

[Module Storage](/api/latest/storage.md#module) is useful for flows that are
importable from a Python module. If you package your flows as part of a Python
module, you can use `Module` storage to reference and load them at execution
time (provided the module is installed and importable in the execution
environment).

```python
from prefect import Flow
from prefect.storage import Module

flow = Flow("module example", storage=Module("mymodule.flows"))

# Tip: you can use `__name__` to automatically reference the current module.
flow = Flow("module example", storage=Module(__name__))
```

### AWS S3

[S3 Storage](/api/latest/storage.md#s3) is a storage option that
saves flows to and references flows stored in an AWS S3 bucket.

```python
from prefect import Flow
from prefect.storage import S3

flow = Flow("s3-flow", storage=S3(bucket="<my-bucket>"))
```

After registration, the flow will be stored in the specified bucket under
`<slugified-flow-name>/<slugified-current-timestamp>`.

!!! tip Flow Results
Flows configured with `S3` storage also default to using a `S3Result` for
persisting any task results in the same S3 bucket.
:::

!!! tip AWS Credentials
    S3 Storage uses AWS credentials the same way as
    [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html),
    which means both upload (build) and download (local agent) times need to have
    proper AWS credential configuration.
:::

### Azure Blob Storage

[Azure Storage](/api/latest/storage.md#azure) is a storage
option that saves flows to and references flows stored in an Azure Blob container.

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

!!! tip Flow Results
    Flows configured with `Azure` storage also default to using an `AzureResult` for
    persisting any task results to the same container in Azure Blob storage.
:::

!!! tip Azure Credentials
    Azure Storage uses an Azure [connection
    string](https://docs.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string),
    which means both upload (build) and download (local agent) times need to have a
    working Azure connection string. Azure Storage will also look in the
    environment variable `AZURE_STORAGE_CONNECTION_STRING` if it is not passed to
    the class directly.
:::

### Google Cloud Storage

[GCS Storage](/api/latest/storage.md#gcs) is a storage option
that saves flows to and references flows stored in a Google Cloud Storage bucket.

```python
from prefect import Flow
from prefect.storage import GCS

flow = Flow("gcs-flow", storage=GCS(bucket="<my-bucket>"))
```

After registration the flow will be stored in the specified bucket under
`<slugified-flow-name>/<slugified-current-timestamp>`.

!!! tip Flow Results
    Flows configured with `GCS` storage also default to using a `GCSResult` for
    persisting any task results in the same GCS location.
:::

!!! tip Google Cloud Credentials
    GCS Storage uses Google Cloud credentials the same way as the standard
    [google.cloud
    library](https://cloud.google.com/docs/authentication/production#auth-cloud-implicit-python),
    which means both upload (build) and download (local agent) times need to have
    the proper Google Application Credentials configuration.
:::

!!! tip Extra dependency
    You need to install `google` PIP extra (`pip install prefect[google]`) to use
    GCS Storage.
:::

### Git
[Git Storage](/api/latest/storage.md#git) is a storage option for referencing flows
stored in a git repository as `.py` files.

This storage class uses underlying git protocol instead of specific client libraries (such as `PyGithub` for GitHub), superseding other git-based storages.

```python
from prefect import Flow
from prefect.storage import Git

# using https by default
storage = Git(
    repo="org/repo",                            # name of repo
    flow_path="flows/my_flow.py",               # location of flow file in repo
    repo_host="github.com",                     # repo host name
    git_token_secret_name="MY_GIT_ACCESS_TOKEN" # name of personal access token secret
)

# using ssh, including Deploy Keys
# (environment must be configured for ssh access to repo)
storage = Git(
    repo="org/repo",                            # name of repo
    flow_path="flows/my_flow.py",               # location of flow file in repo
    repo_host="github.com",                     # repo host name
    use_ssh=True                                # use ssh for cloning repo
)
```

`Git` storage will attempt to build the correct `git clone` URL based on the parameters provided. Users can override this logic and provide their `git clone` URL directly.

To use a custom `git clone` URL, first create a `Secret` containing the URL. Then specify the name of the secret when creating your `Git` storage class.

```python
# example using Azure devops URL
# using a secret named 'MY_REPO_CLONE_URL' with value 'https://<username>:<personal_access_token>@dev.azure.com/<organization>/<project>/_git/<repo>'

storage = Git(
    flow_path="flows/my_flow.py",
    git_clone_url_secret_name="MY_REPO_CLONE_URL" # use the value of this secret to clone the repository
)
```

##### Git Deploy Keys

To use `Git` storage with Deploy Keys, ensure your environment is configured to use Deploy Keys. Then, create a `Git` storage class with `use_ssh=True`.

You can find more information about configuring Deploy Keys for common providers here:

- [GitHub](https://docs.github.com/en/developers/overview/managing-deploy-keys#deploy-keys)
- [GitLab](https://docs.gitlab.com/ee/user/project/deploy_keys/)
- [BitBucket](https://bitbucket.org/blog/deployment-keys)

For Deploy Keys to work correctly, the flow execution environment must be configured to clone a repository using SSH.
This configuration is not Prefect specific and varies across infrastructure.

For more information and examples, see [configuring SSH + Git storage](/orchestration/flow_config/storage.html#ssh-git-storage).


#### GitLab Deploy Tokens

To use `Git` storage with GitLab Deploy Tokens, first create a Secret storing your Deploy Token. Then, you can configure `Git` storage:

```python
storage = Git(
    repo="org/repo",                            # name of repo
    flow_path="flows/my_flow.py",               # location of flow file in repo
    repo_host="gitlab.com",                     # repo host name, which may be custom
    git_token_secret_name="MY_GIT_ACCESS_TOKEN",# name of Secret containing Deploy Token
    git_token_username="myuser"                 # username associated with the Deploy Token
)
```


!!! tip Loading additional files from a git repository
    `Git` storage allows you to load additional files alongside your flow file. For more information, see [Loading Additional Files with Git Storage](/orchestration/flow_config/storage.html#loading-additional-files-with-git-storage).
:::

### GitHub

[GitHub Storage](/api/latest/storage.md#github) is a storage
option for referencing flows stored in a GitHub repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import GitHub

flow = Flow(
    "github-flow",
    GitHub(
        repo="org/repo",                           # name of repo
        path="flows/my_flow.py",                   # location of flow file in repo
        access_token_secret="GITHUB_ACCESS_TOKEN"  # name of personal access token secret
    )
)
```

For a detailed look on how to use GitHub storage see the [Using script based
storage](/core/idioms/script-based.md) idiom.

!!! tip GitHub Credentials
    When used with private repositories, GitHub storage requires configuring a
    [personal access
    token](https://docs.github.com/en/github/authenticating-to-github/creating-a-personal-access-token).
    This token should have `repo` scope, and will be used to read the flow's source
    from its respective repository.
:::

### GitLab

[GitLab Storage](/api/latest/storage.md#gitlab) is a storage
option for referencing flows stored in a GitLab repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import GitLab

flow = Flow(
    "gitlab-flow",
    GitLab(
        repo="org/repo",                           # name of repo
        path="flows/my_flow.py",                   # location of flow file in repo
        access_token_secret="GITLAB_ACCESS_TOKEN"  # name of personal access token secret
    )
)
```

Much of the GitHub example in the [script based
storage](/core/idioms/script-based.md) documentation applies to GitLab as well.

!!! tip GitLab Credentials
    GitLab storage uses a [personal access
    token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) for
    authenticating with repositories.
:::

!!! tip GitLab Server
    GitLab server users can point the `host` argument to their personal GitLab
    instance.
:::

### Bitbucket

[Bitbucket Storage](/api/latest/storage.html#bitbucket) is a
storage option that uploads flows to a Bitbucket repository as `.py` files.

```python
from prefect import Flow
from prefect.storage import Bitbucket

flow = Flow(
    "bitbucket-flow",
    Bitbucket(
        project="project",                            # name of project
        repo="project.repo",                          # name of repo in project
        path="flows/my_flow.py",                      # location of flow file in repo
        access_token_secret="BITBUCKET_ACCESS_TOKEN"  # name of personal access token secret
    )
)
```

Much of the GitHub example in the [script based
storage](/core/idioms/script-based.html) documentation applies to Bitbucket as well.

!!! tip Bitbucket Credentials
    Bitbucket storage uses a [personal access
    token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)
    for authenticating with repositories.
:::

!!! tip Bitbucket Projects
    Unlike GitHub or GitLab, Bitbucket organizes repositories in Projects and each repo
    must be associated with a Project. Bitbucket storage requires a `project` argument
    pointing to the correct project name.
:::

### CodeCommit

[CodeCommit Storage](/api/latest/storage.html#codecommit) is a
storage option for referencing flows stored in a CodeCommit repository as `.py` files.

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

!!! tip AWS Credentials
    CodeCommit uses AWS credentials the same way as
    [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
    which download (local agent) times need to
    have proper AWS credential configuration.
:::

### Docker

[Docker Storage](/api/latest/storage.md#docker) is a storage option that puts
flows inside of a Docker image and pushes them to a container registry. As
such, it will not work with flows deployed via a [local
agent](/orchestration/agents/local.md), since Docker images aren't supported
there.

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
type of container registry uses a different format for image naming (for example, DockerHub or GCR).

If you do not specify a `registry_url` for your Docker Storage, then the image
will not attempt to be pushed to a container registry and instead the image
will live only on your local machine. This is useful when using the Docker
Agent because it will not need to perform a pull of the image since it already
exists locally.

!!! tip Container Registry Credentials
    Docker Storage uses the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/index.html) to build the
    image and push to a registry. Make sure you have the Docker daemon running
    locally and you are configured to push to your desired container registry.
    Additionally, make sure whichever platform Agent deploys the container also has
    permissions to pull from that same registry.
:::

### Webhook

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
`SOME_TOKEN` and then fall back to [Prefect Secrets](/core/concepts/secrets.md) 
`SOME_TOKEN`. Because this resolution is
at runtime, this storage option never has your sensitive information stored in
it and that sensitive information is never sent to Prefect Cloud.

## Loading Additional Files with Git Storage

`Git` storage clones the full repository when loading a flow from storage. This allows you to load non-Python files that live alongside your flow in your repository. For example, you may have a `.sql` file containing a query run in your flow that you want to use in one of your tasks.

To get the file path of your flow, use Python's `__file__` builtin.

For example, let's say we want to say hello to a person and their name is specified by a `.txt` file in our repository.

Our git repository contains two files in the root directory, `flow.py` and `person.txt`.

`flow.py` contains our flow, including logic for loading information from `person.txt`, and should look like this:

```python
from pathlib import Path

import prefect
from prefect import task, Flow
from prefect.storage import Git

# get the path to the flow file using pathlib and __file__
# this path is dynamically populated when the flow is loaded from storage
file_path = Path(__file__).resolve().parent

# using our flow path, load the file
with open(str(file_path) + '/person.txt', 'r') as my_file:
        name = my_file.read()

@task
def say_hello(name):
        logger = prefect.context.get("logger")
        logger.info(f"Hi {name}")

with Flow("my-hello-flow") as flow:
        say_hello(name)

# configure our flow to use `Git` storage
flow.storage = Git(flow_path="flow.py", repo='org/repo')
```

## SSH + Git Storage

To use SSH with `Git` storage, you'll need to ensure your repository can be cloned using SSH from where your flow is being run.

For this to work correctly, the environment must have:

1. An SSH client available
2. Required SSH keys configured


### Adding SSH client to Docker images

When using Docker images, please note the Prefect image does not include an SSH client by default. You will need to build a custom image that includes an SSH client. 

The easiest way to do accomplish this is to add `openssh-client` to a Prefect image.

```dockerfile
FROM prefecthq/prefect:latest
RUN apt update && apt install -y openssh-client
```

You can configure your flow to use the new image via the `image` field in your flow's [run config](/orchestration/flow_config/run_configs.html).

### Configuring SSH keys

SSH keys should be mounted to the `/root/.ssh` directory. If using a custom image not based on `prefecthq/prefect:latest`, this may change.

*Please note management of SSH keys presents significant security challenges. The following examples may not represent industry best practice.*

#### Docker agent - mounting SSH keys as volumes

When using a [Docker agent](/orchestration/agents/docker.html#docker-agent), SSH keys can be mounted as volumes at run time using the `--volume` flag.

```bash
prefect agent docker start --volume /path/to/ssh_directory:/root/.ssh
```

#### Kubernetes agent - mounting SSH keys as Kubernetes Secrets

When using a [Kubernetes agent](/orchestration/agents/kubernetes.html#kubernetes-agent), SSH keys can be mounted as secret volumes.

First, create a [Kubernetes Secret](https://kubernetes.io/docs/concepts/configuration/secret/) containing your SSH key and known hosts file.

```bash
kubectl create secret generic my-ssh-key --from-file=<ssh-key-name>=/path/to/<ssh-key-name> --from-file=known_hosts=/path/to/known_hosts
```

Next, create a custom job template to mount the secret volume to `/root/.ssh`.

```yaml
apiVersion: batch/v1
kind: Job
spec:
  template:
    spec:
      containers:
        - name: flow
          volumeMounts:
            - name: ssh-key
              readOnly: true
              mountPath: "/root/.ssh"
      volumes:
        - name: ssh-key
          secret:
            secretName: my-ssh-key
            optional: false
            defaultMode: 0600
```

Finally, [configure the agent or flow to use the custom job template](https://docs.prefect.io/orchestration/agents/kubernetes.html#custom-job-template). 


Creating a [Kubernetes service account](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/) to permission the Secret properly is recommended. Once configured in Kubernetes, service account can be set either [on agent start or on the run config](https://docs.prefect.io/orchestration/agents/kubernetes.html#service-account).
