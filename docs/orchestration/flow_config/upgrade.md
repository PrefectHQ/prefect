# Upgrading from Prefect < 0.14.0

Prefect 0.14.0 included a new Flow configuration system based on
[RunConfig](./run_configs.md) objects. This replaces the previous system based
on [Environment](/orchestration/execution/overview.md) objects, with
`Environment` based configuration being deprecated in 0.14.0 and removed in 1.0.0.

If you never configured `flow.environment` explicitly on your flow, your
upgrade process should be seamless. Your flows will automatically transition to
use the new `flow.run_config` system.

If you did set an `Environment` explicitly on a flow, you'll want to transition
your flows to use an equivalent `RunConfig`. Below we'll outline a few common
environment setups, and their equivalents using run-configs.

## LocalEnvironment

`LocalEnvironment` was the default environment in previous versions of Prefect.
It would execute flow runs in the same process started by the agent.

The name was confusing to many users, since `LocalEnvironment` didn't require
using the `LocalAgent` (it worked with any agent). This also meant that the
`LocalEnvironment` couldn't easily contain any platform-specific configuration.

In contrast, [RunConfig](./run_configs.md) objects correspond to a specific
agent type (e.g. `LocalRun` for `LocalAgent`, `KuberenetesRun` for
`KubernetesAgent`, ...), and contain platform-specific configuration options
(e.g. `image`, ...). The exception to this is
[UniversalRun](./run_configs.md#universalrun), which works with any agent (but
only contains configuration for setting [labels](./run_config.md#labels)).

`LocalEnvironment` also contained an option to configure an
[Executor](./executors.md) for the flow run - this option has been moved to
the `Flow` itself. See [Executor](./executors.md) for more information.

- If you configured an `Executor` on your `LocalEnvironment`, move that setting
  to the flow itself.

  ```python
  # Replace this
  from prefect.executors import DaskExecutor
  from prefect.environments.execution import LocalEnvironment
  flow.environment = LocalEnvironment(executor=DaskExecutor())

  # With this
  from prefect.executors import DaskExecutor
  flow.executor = DaskExecutor()
  ```

- If you only need to configure flow `labels`, you should use a
  [UniversalRun](./run_configs.md#universalrun).

  ```python
  # Replace this
  from prefect.environments.execution import LocalEnvironment
  flow.environment = LocalEnvironment(labels=["label-1", "label-2"])

  # With this
  from prefect.run_configs import UniversalRun
  flow.run_config = UniversalRun(labels=["label-1", "label-2"])
  ```

- If you need to configure platform-specific settings (e.g. an `image`), you
  should use the run-config that corresponds to your agent. For example, if
  using the Kubernetes Agent you'd use a
  [KubernetesRun](./run_configs.md#kubernetesrun):

  ```python
  # Replace this
  from prefect.environments.execution import LocalEnvironment
  flow.environment = LocalEnvironment(metadata={"image": "my-image"})

  # With this
  from prefect.run_configs import KubernetesRun
  flow.run_config = KubernetesRun(image="my-image")
  ```

  The different `RunConfig` types support different platform-specific settings
  that you may be interested in - see the [RunConfig docs](./run_configs.md)
  for more info.

## KubernetesJobEnvironment

`KubernetesJobEnvironment` provided support for configuring details of a
Kubernetes Job on a Flow. This has been replaced with
[KubernetesRun](./run_configs.md#kubernetesrun).

Unlike `KubernetesJobEnvironment`, which only accepted a custom job spec stored
as a local file, `KubernetesRun` accepts custom job specs stored locally, in
memory (you can pass in a dict/yaml directly), or stored on a remote filesystem
(S3 or GCS). There are also options for common settings (e.g.  `image`,
`cpu_request`/`cpu_limit`, `memory_request`/`memory_limit`, ...). See the
examples in the [KubernetesRun docs](./run_configs.md#kubernetesrun) for more
information.

- If you configured an `Executor` on your `KubernetesJobEnvironment`, move that
  setting to the flow itself.

  ```python
  # Replace this
  from prefect.executors import DaskExecutor
  from prefect.environments.execution import KubernetesJobEnvironment
  flow.environment = KubernetesJobEnvironment(executor=DaskExecutor())

  # With this
  from prefect.executors import DaskExecutor
  flow.executor = DaskExecutor()
  ```

- If you provided a custom job spec file, you can convert directly by passing
  in `job_template_path` to `KubernetesRun`. Depending on what you're
  configuring, you may find the other arguments to `KubernetesRun` a better fit
  for your needs, see the [KubernetesRun docs](./run_configs.md#kubernetesrun)
  for more information.

  ```python
  # Replace this
  from prefect.environments.execution import KubernetesJobEnvironment
  flow.environment = KubernetesJobEnvironment(job_spec_file="path/to/file.yaml")

  # With this
  from prefect.run_configs import KubernetesRun
  flow.run_config = KubernetesRun(job_spec_file="path/to/file.yaml")
  ```

## FargateTaskEnvironment

`FargateTaskEnvironment` provided support for configuring details of a
Fargate Task on a Flow. This has been replaced with
[ECSRun](./run_configs.md#ecsrun).

`ECSRun` has similar config options as `FargateTaskEnvironment`, but also
exposes raw configuration options for both
[registering](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition)
and
[running](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task)
ECS tasks. There are also options for common settings (e.g.  `image`, `cpu`,
`memory`, ...). See the examples in the [ECSRun docs](./run_configs.md#ecsrun)
for more information.

Note that use of `ECSRun` requires running an [ECS
Agent](/orchestration/agents/ecs.md), not the deprecated [Fargate
Agent](/orchestration/agents/fargate.md).

- If you configured an `Executor` on your `FargateTaskEnvironment`, move that
  setting to the flow itself.

  ```python
  # Replace this
  from prefect.executors import DaskExecutor
  flow.environment = FargateTaskEnvironment(executor=DaskExecutor())

  # With this
  from prefect.executors import DaskExecutor
  flow.executor = DaskExecutor()
  ```

- `ECSRun` (coupled with the [ECS Agent](/orchestration/agents/ecs.md))
  supports configuring ECS Tasks at a finer level than before. If you
  previously configured custom task definitions on the [Fargate
  Agent](/orchestration/agents/fargate.md), you may be better served by
  specifying these options via `ECSRun` objects instead. See the [ECSRun API
  docs](/api/latest/run_configs.md#ecsrun) for a complete list of available
  options.


## DaskKubernetesEnvironment

`DaskKubernetesEnvironment` provided support for running Prefect on Kubernetes
with Dask. With the 0.14.0 release, this would be replaced with

- A [KubernetesRun](./run_config.md#kubernetesrun) run-config for configuring
  the initial flow-runner pod.
- A [DaskExecutor](./executors.md#daskexecutor) configured to create a
  temporary cluster using [dask-kubernetes](https://kubernetes.dask.org).

We split this configuration into two parts to make it easier to mix-and-match
and enable deeper customization. One downside is that the configuration is a
bit more verbose, but hopefully still relatively straightforward.

```python
# Replace this
from prefect.environments.execution import DaskKubernetesEnvironment
flow.environment = DaskKubernetesEnvironment(
    min_workers=5, max_workers=10,
)

# With this
import prefect
from prefect.executors import DaskExecutor
from prefect.run_configs import KubernetesRun
from dask_kubernetes import KubeCluster, make_pod_spec
# Configuration for the flow-runner pod goes here
flow.run_config = KubernetesRun()
# Configuration for the Dask cluster goes here
# - `cluster_class` takes any callable to create a new cluster. We define our
#    own helper function to forward the image name to be the same one used to
#    deploy the main flow-runner pod.
# - `adapt_kwargs` takes a dict of kwargs to pass to `cluster.adapt`. Here
#    we enable adaptive scaling between 5 and 10 workers.
flow.executor = DaskExecutor(
    cluster_class=lambda: KubeCluster(make_pod_spec(image=prefect.context.image)),
    adapt_kwargs={"minimum": 5, "maximum": 10},
)
```

With the above, you should have full customization of all Kubernetes objects
created to execute the flow run. For more information on the various options,
please see:

- [KubernetesRun docs](./run_configs.md#kubernetesrun)
- [DaskExecutor docs](./run_config.md#daskexecutor)
- [dask-kubernetes docs](https://kubernetes.dask.org)


## DaskCloudProviderEnvironment

`DaskCloudProviderEnvironment` provided support for running Prefect on various
cloud providers (originally just AWS ECS) with Dask using
[dask-cloudprovider](https://cloudprovider.dask.org). With the 0.14.0 release,
this might be replaced with

- An [ECSRun](./run_config.md#ecsrun) run-config for configuring
  the initial flow-runner pod.
- A [DaskExecutor](./executors.md#daskexecutor) configured to create a
  temporary cluster using [dask-cloudprovider](https://cloudprovider.dask.org).

We split this configuration into two parts to make it easier to mix-and-match
and enable deeper customization. One downside is that the configuration is a
bit more verbose, but hopefully still relatively straightforward.

```python
# Replace this
from prefect.environments.execution import DaskCloudProviderEnvironment
flow.environment = DaskCloudProviderEnvironment(
    adaptive_min_workers=5, adaptive_max_workers=10,
)

# With this
import prefect
from prefect.executors import DaskExecutor
from prefect.run_configs import ECSRun
from dask_cloudprovider.aws import FargateCluster
# Configuration for the flow-runner task goes here
flow.run_config = ECSRun()
# Configuration for the Dask cluster goes here
# - `cluster_class` takes any callable to create a new cluster. We define our
#    own helper function to forward the image name to be the same one used to
#    deploy the main flow-runner task. If you statically know the image name,
#    you could skip the lambda and pass in:
#    
#    DaskExecutor(cluster_class=FargateCluster, cluster_kwargs={"image": "my-image"})
#    
# - `adapt_kwargs` takes a dict of kwargs to pass to `cluster.adapt`. Here
#    we enable adaptive scaling between 5 and 10 workers.
flow.executor = DaskExecutor(
    cluster_class=lambda: FargateCluster(image=prefect.context.image),
    adapt_kwargs={"minimum": 5, "maximum": 10},
)
```

With the above, you should have full customization of all AWS objects created
to execute the flow run. For more information on the various options, please
see:

- [ECSRun docs](./run_configs.md#ecsrun)
- [DaskExecutor docs](./run_config.md#daskexecutor)
- [dask-cloudprovider docs](https://cloudprovider.dask.org)
