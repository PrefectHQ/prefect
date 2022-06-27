# Run Configuration

`RunConfig` objects define where and how a flow run should be executed. Each
`RunConfig` type has a corresponding Prefect Agent (i.e. `LocalRun` pairs with
a Local Agent, `DockerRun` pairs with a Docker Agent, ...). The options
available on a `RunConfig` depend on the type, but generally include options
for setting environment variables, configuring resources (CPU/memory), or
selecting a [docker image](./docker.md) to use (if not using `Docker` storage).

To configure a Flow's `run_config`, you can either specify the `run_config` as
part of the `Flow` constructor, or set it as an attribute later before calling
`flow.register`. For example, to configure a flow to run on Kubernetes:

```python
from prefect import Flow
from prefect.run_configs import KubernetesRun

# Set run_config as part of the constructor
with Flow("example", run_config=KubernetesRun()) as flow:
    ...

# OR set run_config as an attribute later
with Flow("example") as flow:
    ...

flow.run_config = KubernetesRun()
```

`RunConfig` objects and their properties can also be overridden for
individual flow runs in the Prefect UI.

## Labels

[Like Agents](../agents/overview.md#labels), `RunConfig` objects can be
configured with zero or more labels.  Labels can be used to determine which
agent (or agents) can execute a flow; for an agent to receive a flow run to
execute, the labels set on the agent must be a *superset* of those set on the
`RunConfig`.

For example, here we configure a flow with `labels=["dev", "ml"]`:

```python
from prefect import Flow
from prefect.run_configs import LocalRun

# Configure a flow with a `dev` label
flow = Flow(
    "example",
    run_config=LocalRun(labels=["dev", "ml"])
)
```

An agent running with `labels=["dev", "staging", "ml"]` would be able to
execute this flow, since the agent's labels are a *superset* of those on the
flow. In contrast, an agent running with `labels=["dev", "staging"]` would
not, since the agent's labels are not a *superset* of those on the flow.

!!! tip Empty Labels
    An empty label list is effectively considered a label. This means that if you
    register a flow with no labels it will only be picked up by Agents which also
    do not have labels specified.
:::

## Types

Prefect has a number of different `RunConfig` implementations - we'll briefly
cover each below. See [the API
documentation](/api/latest/run_configs.md) for more information.

### UniversalRun

[UniversalRun](/api/latest/run_configs.md#universalrun) configures
flow runs that can be deployed on any agent. This is the default `RunConfig`
used if flow-labels are specified. It can be useful if agent-side configuration
is sufficient. Only configuring environment variables and the flow's labels is exposed - to configure
backend specific fields use one of the other `RunConfig` types.

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import UniversalRun

flow.run_config = UniversalRun()
```

Configure environment variables and labels for this flow:

```python
flow.run_config = UniversalRun(env={"SOME_VAR": "value"}, ["label-1", "label-2"])
```

### LocalRun

[LocalRun](/api/latest/run_configs.md#localrun) configures flow
runs deployed as local processes with a
[LocalAgent](/orchestration/agents/local.md).

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import LocalRun

flow.run_config = LocalRun()
```

Set an environment variable in the flow run process:

```python
flow.run_config = LocalRun(env={"SOME_VAR": "value"})
```

Run in a specified working directory:

```python
flow.run_config = LocalRun(working_dir="/path/to/working-directory")
```

### DockerRun

[DockerRun](/api/latest/run_configs.md#dockerrun) configures flow
runs deployed as docker containers with a
[DockerAgent](/orchestration/agents/docker.md).

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import DockerRun

flow.run_config = DockerRun()
```

Set an environment variable in the flow run container:

```python
flow.run_config = DockerRun(env={"SOME_VAR": "value"})
```

Specify a [docker image](./docker.md) to use, if not using `Docker` storage:

```python
flow.run_config = DockerRun(image="example/image-name:with-tag")
```

### KubernetesRun

[KubernetesRun](/api/latest/run_configs.md#kubernetesrun)
configures flow runs deployed as Kubernetes jobs with a
[KubernetesAgent](/orchestration/agents/kubernetes.md).

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import KubernetesRun

flow.run_config = KubernetesRun()
```

Set an environment variable in the flow run container:

```python
flow.run_config = KubernetesRun(env={"SOME_VAR": "value"})
```

Specify an [image](./docker.md) to use, if not using `Docker` storage:

```python
flow.run_config = KubernetesRun(image="example/image-name:with-tag")
```

Specify custom [resource
requests](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#requests-and-limits)
for this flow:

```python
flow.run_config = KubernetesRun(cpu_request=2, memory_request="2Gi")
```

Use a custom Kubernetes Job spec for this flow, stored in S3:

```python
flow.run_config = KubernetesRun(job_template_path="s3://bucket/path/to/spec.yaml")
```

Specify an [imagePullPolicy](https://kubernetes.io/docs/concepts/configuration/overview/#container-images) 
for the Kubernetes job:


```python
flow.run_config = KubernetesRun(image_pull_policy="Always")
````

### ECSRun

[ECSRun](/api/latest/run_configs.md#ecsrun) configures flow runs
deployed as ECS tasks with a ECSAgent.

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import ECSRun

flow.run_config = ECSRun()
```

Set an environment variable in the flow run container:

```python
flow.run_config = ECSRun(env={"SOME_VAR": "value"})
```

Specify an [image](./docker.md) to use, if not using `Docker` storage:

```python
flow.run_config = ECSRun(image="example/image-name:with-tag")
```

Specify CPU and memory available for this flow:

```python
flow.run_config = ECSRun(cpu="2 vcpu", memory="4 GB")
```

Use a custom [task
definition](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition)
for this flow, stored in S3:

```python
flow.run_config = ECSRun(task_definition_path="s3://bucket/path/to/definition.yaml")
```

### VertexRun

[VertexRun](/api/latest/run_configs.md#vertexrun) configures flow runs
deployed as Vertex CustomJobs with a VertexAgent.

#### Examples

Use the defaults set on the agent:

```python
from prefect.run_configs import VertexRun

flow.run_config = VertexRun()
```

Set an environment variable in the flow run container:

```python
flow.run_config = VertexRun(env={"SOME_VAR": "value"})
```

Specify an [image](./docker.md) to use, if not using `Docker` storage. If you're using `Docker` storage, then
that image will be used. If you do not use docker storage or provide an image in the run config, then the run
will use the default `prefect` image.

```python
flow.run_config = VertexRun(image="example/image-name:with-tag")
```

Specify the machine type for this flow

```python
flow.run_config = VertexRun(machine_type='e2-highmem-16')
```

Set a specific service account or network ID for this flow run
```python
flow.run_config = VertexRun(service_account='my-account@my-project.iam.gserviceaccount.com', network="my-network")
```

Use the [scheduling](https://cloud.google.com/vertex-ai/docs/reference/rest/v1/CustomJobSpec#Scheduling) option to set a timeout for the CustomJob
```python
flow.run_config = VertexRun(scheduling={'timeout': '3600s'})
```


Customize the full [worker pool specs](https://cloud.google.com/vertex-ai/docs/reference/rest/v1/CustomJobSpec#workerpoolspec),
which can be used for more advanced setups:

```python
worker_pool_specs = [
    {"machine_spec": {"machine_type": "e2-standard-4"}, "replica_count": 1},
    {
        "machine_spec": {"machine_type": "e2-highmem-16"},
        "replica_count": 3,
        "container_spec": {"image": "my-image"},
    },
]

flow.run_config = VertexRun(worker_pool_specs=worker_pool_specs)
```

!!! warning Container Spec 
    Prefect will always control the container spec on the 0th entry in the worker pool spec,
    which is the pool that is reserved to run the flow. You will need to provide a container
    spec for any other worker pool specs.
:::
