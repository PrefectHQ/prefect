---
description: Prefect infrastructure responsible for creating and monitoring the execution environment for flow runs associated with deployments.
tags:
    - orchestration
    - infrastructure
    - flow run infrastructure
    - deployments
    - Kubernetes
    - Docker
---

# Infrastructure

Users may specify an [infrastructure](/api-ref/prefect/infrastructure/) block when creating a deployment. This block will be used to specify infrastructure for flow runs created by the deployment at runtime.

Infrastructure can only be used with a [deployment](/concepts/deployments/). When you run a flow directly by calling the flow yourself, you are responsible for the environment in which the flow executes.

## Infrastructure overview

Prefect uses infrastructure to create the environment for a user's flow to execute.

Infrastructure is attached to a deployment and is propagated to flow runs created for that deployment. Infrastructure is deserialized by the agent and it has two jobs:

- Create execution environment infrastructure for the flow run.
- Run a Python command to start the `prefect.engine` in the infrastructure, which retrieves the flow from storage and executes the flow.

The engine acquires and calls the flow. Infrastructure doesn't know anything about how the flow is stored, it's just passing a flow run ID to the engine.

Infrastructure is specific to the environments in which flows will run. Prefect currently provides the following infrastructure types:

- [`Process`](/api-ref/prefect/infrastructure/#prefect.infrastructure.process.Process) runs flows in a local subprocess.
- [`DockerContainer`](/api-ref/prefect/infrastructure/#prefect.infrastructure.docker.DockerContainer) runs flows in a Docker container.
- [`KubernetesJob`](/api-ref/prefect/infrastructure/#prefect.infrastructure.kubernetes.KubernetesJob) runs flows in a Kubernetes Job.

!!! question "What about tasks?"
    Flows and tasks can both use configuration objects to manage the environment in which code runs. 
    
    Flows use infrastructure.
    
    Tasks use task runners. For more on how task runners work, see [Task Runners](/concepts/task-runners/).

## Using infrastructure

You may create customized infrastructure blocks through the Prefect UI or Prefect Cloud [Blocks](/ui/blocks/) page or create them in code and save them to the API using the blocks [`.save()`](/api-ref/prefect/blocks/core/#prefect.blocks.core.Block.save) method.

Once created, there are two distinct ways to use infrastructure in a deployment: 

- Starting with Prefect defaults &mdash; this is what happens when you pass  the `-i` or `--infra` flag and provide a type when building deployment files.
- Pre-configure infrastructure settings as blocks and base your deployment infrastructure on those settings &mdash; by passing `-ib` or `--infra-block` and a block slug when building deployment files.

For example, when creating your deployment files, the supported Prefect infrastrucure types are:

- `process`
- `docker-container`
- `kubernetes-job`

<div class="terminal">
```bash
$ prefect deployment build ./my_flow.py:my_flow -n my-flow-deployment -t test -i docker-container -sb s3/my-bucket
Found flow 'my-flow'
Manifest created at '/Users/terry/test/testflows/infra/my_flow-manifest.json'.
Successfully uploaded 2 files to s3://bucket-full-of-sunshine
Deployment YAML created at '/Users/terry/test/flows/infra/deployment.yaml'.
```
</div>

In this example we specify the `DockerContainer` infrastructure in addition to a preconfigured AWS S3 bucket [storage](/concepts/storage/) block.

The default deployment YAML filename may be edited as needed to add an infrastructure type or infrastructure settings.

```yaml
###
### A complete description of a Prefect Deployment for flow 'my-flow'
###
name: my-flow-deployment
description: null
tags:
- test
schedule: null
parameters: {}
infrastructure:
  type: docker-container
  env: {}
  labels: {}
  name: null
  command:
  - python
  - -m
  - prefect.engine
  image: prefecthq/prefect:dev-python3.9
  image_pull_policy: null
  networks: []
  network_mode: null
  auto_remove: false
  volumes: []
  stream_output: true
###
### DO NOT EDIT BELOW THIS LINE
###
flow_name: my-flow
manifest_path: my_flow-manifest.json
storage:
  bucket_path: bucket-full-of-sunshine
  aws_access_key_id: '**********'
  aws_secret_access_key: '**********'
  _is_anonymous: true
  _block_document_name: anonymous-xxxxxxxx-f1ff-4265-b55c-6353a6d65333
  _block_document_id: xxxxxxxx-06c2-4c3c-a505-4a8db0147011
  _block_type_slug: s3
parameter_openapi_schema:
  title: Parameters
  type: object
  properties: {}
  required: null
  definitions: null
```

!!! note "Editing deployment YAML"
    Note the big **DO NOT EDIT** comment in the deployment YAML: In practice, anything above this block can be freely edited _before_ running `prefect deployment apply` to create the deployment on the API. 

Once the deployment exists, any flow runs that this deployment starts will use `DockerContainer` infrastructure.

You can also create custom infrastructure blocks &mdash; either in the Prefect UI for in code via the API &mdash; and use the settings in the block to configure your infastructure. For example, here we specify settings for Kubernetes infrastructure in a block named `k8sdev`.

```python
from prefect.infrastructure import KubernetesJob, KubernetesImagePullPolicy

k8s_job = KubernetesJob(
    namespace="dev",
    image="prefecthq/prefect:2.0.0-python3.9",
    image_pull_policy=KubernetesImagePullPolicy.IF_NOT_PRESENT,
)
k8s_job.save("k8sdev")
```

Now we can apply the infrastrucure type and settings in the block by specifying the block slug `kubernetes-job/k8sdev` as the infrastructure type when building a deployment:

<div class="terminal">
```bash
prefect deployment build flows/k8s_example.py:k8s_flow --name k8sdev --tag k8s -sb s3/dev -ib kubernetes-job/k8sdev
```
</div>

See [Deployments](/concepts/deployments/) for more information about deployment build options.

## Configuring infrastructure

Every infrastrcture type has type-specific options.

### Process

[`Process`](/api-ref/prefect/infrastructure/#prefect.infrastructure.process.Process) infrastructure runs a command in a new process.

Current environment variables and Prefect settings will be included in the created process. Configured environment variables will override any current environment variables.

`Process` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| command | A list of strings specifying the command to start the flow run. In most cases you should not override this. |
| env	| Environment variables to set for the new process. |
| labels	| Labels for the process. Labels are for metadata purposes only and cannot be attached to the process itself. |
| name	| A name for the process. For display purposes only. |


## DockerContainer

[`DockerContainer`](/api-ref/prefect/infrastructure/#prefect.infrastructure.docker.DockerContainer) infrastructure  executes flow runs in a container.

Requirements for `DockerContainer`:

- Docker Engine must be available.
- You must configure remote [Storage](/concepts/storage/). Local storage is not supported for Docker.
- The API must be available from within the flow run container. To facilitate connections to locally hosted APIs, `localhost` and `127.0.0.1` will be replaced with `host.docker.internal`.
- The ephemeral Orion API won't work with Docker and Kubernetes. You must have an Orion or Prefect Cloud API endpoint set in your [agent's configuration](/concepts/work-queues/).

`DockerContainer` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| auto_remove | Bool indicating whether the container will be removed on completion. If False, the container will remain after exit for inspection. |
| command | A list of strings specifying the command to run in the container to start the flow run. In most cases you should not override this. |
| env	| Environment variables to set for the container. |
| image | An optional string specifying the tag of a Docker image to use. Defaults to the Prefect image. |
| image_pull_policy | Specifies if the image should be pulled. One of 'ALWAYS', 'NEVER', 'IF_NOT_PRESENT'. |
| labels | An optional dictionary of labels, mapping name to value. |
| name | An optional name for the container. |
| networks | An optional list of strings specifying Docker networks to connect the container to. |
| network_mode | Set the network mode for the created container. Defaults to 'host' if a local API url is detected, otherwise the Docker default of 'bridge' is used. If 'networks' is set, this cannot be set. | 
| stream_output | Bool indicating whether to stream output from the subprocess to local standard output. |
| volumes | An optional list of volume mount strings in the format of "local_path:container_path". |

Prefect automatically sets a Docker image matching the Python and Prefect version you're using at deployment time. You can see all available images at [Docker Hub](https://hub.docker.com/r/prefecthq/prefect/tags?page=1&name=2.0).

## KubernetesJob

[`KubernetesJob`](/api-ref/prefect/infrastructure/#prefect.infrastructure.kubernetes.KubernetesJob) infrastructure executes flow runs in a Kubernetes Job.

Requirements for `KubernetesJob`:

- `kubectl` must be available.
- You must configure remote [Storage](/concepts/storage/). Local storage is not supported for Kubernetes.
- The ephemeral Orion API won't work with Docker and Kubernetes. You must have an Orion or Prefect Cloud API endpoint set in your [agent's configuration](/concepts/work-queues/).

The Prefect CLI command `prefect kubernetes manifest orion` automatically generates a Kubernetes manifest with default settings for Prefect deployments. By default, it simply prints out the YAML configuration for a manifest. You can pipe this output to a file of your choice and edit as necessary.

`KubernetesJob` supports the following settings:

| Attributes | Description |
| ---- | ---- |
| command | A list of strings specifying the command to run in the container to start the flow run. In most cases you should not override this. |
| customizations	| A list of JSON 6902 patches to apply to the base Job manifest. |
| env	| Environment variables to set for the container. |
| image | String specifying the tag of a Docker image to use for the Job. |
| image_pull_policy | The Kubernetes image pull policy to use for job containers. |
| job	| The base manifest for the Kubernetes Job. |
| job_watch_timeout_seconds	| Number of seconds to watch for job creation before timing out (default 5). |
| labels | Dictionary of labels to add to the Job. |
| name | An optional name for the job. |
| namespace | String signifying the Kubernetes namespace to use. |
| pod_watch_timeout_seconds	| Number of seconds to watch for pod creation before timing out (default 5). |
| restart_policy | The Kubernetes restart policy to use for Jobs. |
| service_account_name	| An optional string specifying which Kubernetes service account to use. | 
| stream_output | Bool indicating whether to stream output from the subprocess to local standard output. |


## Docker images

Prefect agents rely on Docker images for executing flow runs using `DockerContainer` or `KubernetesJob` infrastructure.

Every release of Prefect comes with a few built-in images. These images are all
named [prefecthq/prefect](https://hub.docker.com/r/prefecthq/prefect), but have
a few different tag options:

### Standard Python

| Tag                   |       Prefect Version       | Python Version  |
| --------------------- | :-------------------------: | -------------:  |
| 2-latest              | most recent v2 PyPi version |            3.10 |
| 2-python3.10          | most recent v2 PyPi version |            3.10 |
| 2-python3.9           | most recent v2 PyPi version |            3.9  |
| 2-python3.8           | most recent v2 PyPi version |            3.8  |
| 2-python3.7           | most recent v2 PyPi version |            3.7  |
| 2.X-python3.10        |             2.X             |            3.10 |
| 2.X-python3.9         |             2.X             |            3.9  |
| 2.X-python3.8         |             2.X             |            3.8  |
| 2.X-python3.7         |             2.X             |            3.7  |
| sha-<hash>-python3.10 |            <hash>           |            3.10 |
| sha-<hash>-python3.9  |            <hash>           |            3.9  |
| sha-<hash>-python3.8  |            <hash>           |            3.8  |
| sha-<hash>-python3.7  |            <hash>           |            3.7  |
| sha-<hash>-python3.7  |            <hash>           |            3.7  |

### Conda-flavored Python

| Tag                         |       Prefect Version       | Python Version  |
| --------------------------- | :-------------------------: | -------------:  |
| 2-latest-conda              | most recent v2 PyPi version |            3.10 |
| 2-python3.10-conda          | most recent v2 PyPi version |            3.10 |
| 2-python3.9-conda           | most recent v2 PyPi version |            3.9  |
| 2-python3.8-conda           | most recent v2 PyPi version |            3.8  |
| 2-python3.7-conda           | most recent v2 PyPi version |            3.7  |
| 2.X-python3.10-conda        |             2.X             |            3.10 |
| 2.X-python3.9-conda         |             2.X             |            3.9  |
| 2.X-python3.8-conda         |             2.X             |            3.8  |
| 2.X-python3.7-conda         |             2.X             |            3.7  |
| sha-<hash>-python3.10-conda |            <hash>           |            3.10 |
| sha-<hash>-python3.9-conda  |            <hash>           |            3.9  |
| sha-<hash>-python3.8-conda  |            <hash>           |            3.8  |
| sha-<hash>-python3.7-conda  |            <hash>           |            3.7  |
| sha-<hash>-python3.7-conda  |            <hash>           |            3.7  |

### Installing Extra Dependencies at Runtime

If you're using the `prefecthq/prefect` image (or an image based on
`prefecthq/prefect`), you can make use of the `EXTRA_PIP_PACKAGES` environment
variable to install dependencies at runtime. If defined, `pip install
${EXTRA_PIP_PACKAGES}` is executed before the flow run starts.

For production deploys we recommend building a custom image (as described
below). Installing dependencies during each flow run can be costly (since
you're downloading from PyPI on each execution) and adds another opportunity
for failure. Use of `EXTRA_PIP_PACKAGES` can be useful during development
though, as it allows you to iterate on dependencies without building a new
image each time.

### Building your Own Image

If your flow relies on dependencies not found in the default
`prefecthq/prefect` images, you'll want to build your own image. You can either
base it off of one of the provided `prefecthq/prefect` images, or build your
own from scratch.

**Extending the `prefecthq/prefect` image**

Here we provide an example `Dockerfile` for building an image based on
`prefecthq/prefect:2-latest`, but with `scikit-learn` installed.

```dockerfile
FROM prefecthq/prefect:2-latest

RUN pip install scikit-learn
```


## Choosing an Image Strategy

The options described above have different complexity (and performance)
characteristics. For choosing a strategy, we provide the following
recommendations:

- If your flow only makes use of tasks defined in the same file as the flow, or
  tasks that are part of `prefect` itself, then you can rely on the default
  provided `prefecthq/prefect` image.

- If your flow requires a few extra dependencies found on PyPI, we recommend
  using the default `prefecthq/prefect` image and setting `EXTRA_PIP_PACKAGES`
  to install these dependencies at runtime. This makes the most sense for small
  dependencies that are quick to install. If the installation process requires
  compiling code or other expensive operations, you may be better off building
  a custom image instead.

- If your flow (or flows) require extra dependencies or shared libraries, we
  recommend building a shared custom image with all the extra dependencies and
  shared task definitions you need. Your flows can then all rely on the same
  image, but have their source stored externally. This can ease development, as the shared
  image only needs to be rebuilt when dependencies change, not when the flow
  source changes.
