# Dask Kubernetes Environment

!!! warning
    Flows configured with environments are no longer supported. We recommend users transition to using [RunConfig](/orchestration/flow_config/run_configs.html) instead. See the [Flow Configuration](/orchestration/flow_config/overview.md) and [Upgrading Environments to RunConfig](/orchestration/faq/upgrade_environments.md) documentation for more information.
:::

[[toc]]

## Overview

The Dask Kubernetes environment uses the [dask-kubernetes](https://kubernetes.dask.org/en/latest/) library to dynamically spawn Dask clusters on Kubernetes. This environment is intended for use in cases where you do not want a static, long-standing Dask cluster, but would rather have a temporary Dask cluster created for each Flow run. The Dask Kubernetes environment has both low-configuration options to quickly get up and running and the ability to specify completely custom [Pod](https://kubernetes.io/docs/concepts/workloads/pods/pod/) specifications for the Dask scheduler and workers.

_For more information on the Dask Kubernetes environment visit the relevant [API documentation](/api/latest/environments/execution.html#daskkubernetesenvironment)._

## Process

#### Initialization

**Quick Configuration:**

The `DaskKubernetesEnvironment` can optionally accept two worker-dependent arguments `min_workers` and `max_workers`. These options set the minimum and maximum number of workers you want to dynamically scale to for your Dask cluster; these default to 1 and 2 workers respectively.

!!! tip Auto Scaling
    If you do not want your Dask cluster to automatically scale the number of workers between the bounds of `min_workers` and `max_workers` then set the two options to the same value.
:::

!!! warning Private Registries
    When running your flows that are registered with a private container registry, you should either specify the name of an `image_pull_secret` on the flow's `DaskKubernetesEnvironment` or directly set the `imagePullSecrets` on your custom worker/scheduler specs.
:::

**Custom Configuration:**

The `DaskKubernetesEnvironment` also has two optional arguments for loading completely custom scheduler and worker YAML specifications: `scheduler_spec_file` and `worker_spec_file`. These options should be file paths to YAML files containing the spec. On initialization these files will be loaded and stored in the environment; they will _never be sent to Prefect Cloud_ and will exist _only inside your Flow's Docker storage_. You may choose to specify only one of these files as both are not required. It is a common use case for users to only specify a `worker_spec_file` because when using Dask all execution takes place on the workers.

Providing custom YAML configuration is useful in a lot of cases, especially when you may want to control resource usage, node allocation, RBAC, etc.

!!! warning YAML Override
    If you choose to provide any custom YAML spec files they will take precedence over the quick configuration arguments when creating the Dask cluster.
:::

!!! warning Image
    When using the custom YAML spec files it is recommended that you ensure the `image` is the same image name and tag that was built for your Flow on registration. This is to ensure consistency of dependencies for your Flow's execution.

    e.g. If you push a Flow's storage as `gcr.io/dev/etl-flow:0.1.0` then your custom YAML spec should contain `- image: gcr.io/dev/etl-flow:0.1.0`.
:::

#### Requirements

The Dask Kubernetes environment requires [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) to be configured in a way in which it can work with both jobs and pods in its namespace. The Prefect CLI provides a convenient `--rbac` flag for automatically attaching this Role and RoleBinding to the Agent deployment YAML.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: prefect-agent-rbac
rules:
- apiGroups: ["batch", "extensions"]
  resources: ["jobs"]
  verbs: ["*"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["*"]

---

apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: default
  name: prefect-agent-rbac
subjects:
  - kind: ServiceAccount
    name: default
roleRef:
  kind: Role
  name: prefect-agent-rbac
  apiGroup: rbac.authorization.k8s.io
```

#### Setup

!!! warning Deprecated
    As of version `0.11.3` setting `docker_secret` and `private_registry` is deprecated. Image pull secrets should be set on custom YAML for the scheduler and worker pods or directly through the `image_pull_secret` kwarg. For more information on Kubernetes imagePullSecets go [here](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/#create-a-pod-that-uses-your-secret).
:::

The Dask Kubernetes environment setup step is responsible for checking the [Kubernetes Secret](https://kubernetes.io/docs/concepts/configuration/secret/) for a provided `docker_secret` only if `private_registry=True`. If the Kubernetes Secret is not found then it will attempt to create one based off of the value set in the Prefect Secret matching the name specified for `docker_secret`.

_For more information on how Docker registry credentials are used as Kubernetes imagePullSecrets go [here](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)._

#### Execute

Create a new [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) with the configuration provided at initialization of this environment. That Job is responsible for creating a `KubeCluster` object from the `dask_kubernetes` library with the provided configuration. Previously configured custom worker YAML and min/max worker settings are applied at this point as `dask_kubernetes` takes care of automatic worker creation.

Following creation of the Dask cluster, the Flow will be run using the [Dask Executor](/api/latest/executors.html#daskexecutor) pointing to the newly-created Dask cluster. All Task execution will take place on the Dask worker pods.

## Examples

#### Dask Kubernetes Environment w/ Min & Max Workers

The following example will execute your Flow on an auto-scaling Dask cluster in Kubernetes. The cluster will start with a single worker and dynamically scale up to five workers as needed.

```python
from prefect import task, Flow
from prefect.environments import DaskKubernetesEnvironment


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Min / Max Workers Dask Kubernetes Example",
    environment=DaskKubernetesEnvironment(min_workers=1, max_workers=3),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)

```

#### Dask Kubernetes Environment w/ Custom Worker YAML

In this example we specify a custom worker specification. There are a few things of note here:

- The worker YAML is contained in a file called `worker_spec.yaml`. This YAML is placed in the same directory as the Flow and is loaded in your environment with `worker_spec_file="worker_spec.yaml"`.

- The Flow's storage is set to have a registry url, image name, and image tag as `gcr.io/dev/dask-k8s-flow:0.1.0`. Note that this is the same image specified in the YAML.

- The worker spec has `replicas: 2` which means that on creation of the Dask cluster there will be two worker pods for executing the Tasks of your Flow.

```yaml
kind: Pod
metadata:
  labels:
    foo: bar
spec:
  replicas: 2
  restartPolicy: Never
  containers:
    - image: gcr.io/dev/dask-k8s-flow:0.1.0
      imagePullPolicy: IfNotPresent
      args: [dask-worker, --nthreads, "2", --no-bokeh, --memory-limit, 4GB]
      name: dask-worker
      env:
        - name: EXTRA_PIP_PACKAGES
          value: fastparquet git+https://github.com/dask/distributed
      resources:
        limits:
          cpu: "2"
          memory: 4G
        requests:
          cpu: "2"
          memory: 2G
```

```python
from prefect import task, Flow
from prefect.environments import DaskKubernetesEnvironment
from prefect.storage import Docker


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Custom Worker Spec Dask Kubernetes Example",
    environment=DaskKubernetesEnvironment(worker_spec_file="worker_spec.yaml"),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="dask-k8s-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)

```
