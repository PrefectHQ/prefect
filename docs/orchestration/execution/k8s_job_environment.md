# Kubernetes Job Environment

::: warning
Flows configured with environments are no longer supported. We recommend users transition to using [RunConfig](/orchestration/flow_config/run_configs.html) instead. See the [Flow Configuration](/orchestration/flow_config/overview.md) and [Upgrading Environments to RunConfig](/orchestration/faq/upgrade_environments.md) documentation for more information.
:::

[[toc]]

## Overview

The Kubernetes Job Environment is an Environment that runs a Flow on a completely custom [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/). This Environment is intended for use in cases where you want complete control over the Job your Flow runs on. This Environment is commonly used for resource management, node allocation, and sidecar containers.

_For more information on the Kubernetes Job Environment visit the relevant [API documentation](/api/latest/environments/execution.html#kubernetesjobenvironment)._

## Process

#### Initialization

The `KubernetesJobEnvironment` accepts an argument `job_spec_file` which is a string representation of a path to a Kubernetes Job YAML file. On initialization that Job spec file is loaded and stored in the Environment. It will _never be sent to Prefect Cloud_ and will only exist inside your Flow's Docker storage.

#### Setup

The Kubernetes Job Environment has no setup step because there are no infrastructure requirements needed to use this Environment.

#### Execute

Create a new [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) with the configuration provided at initialization of this Environment. That Job is responsible for running the Flow.

#### Job Spec Configuration

There are a few caveats to using the Kubernetes Job Environment that revolve around the format of the provided Job YAML. In the Job specification that you provide, the **first container** listed will be the container that is used to run the Flow. This means that the first container will always be overridden during the `execute` step of this Environment.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: my-prefect-job
  labels:
    identifier: ""
    flow_run_id: ""
spec:
  template:
    metadata:
      labels:
        identifier: ""
    spec:
      containers:
        - name: flow-container
          image: ""
          command: []
          args: []
          env:
            - name: MY_ENV
              value: foo
```

In the above YAML block, `flow-container` will be changed during execution:

- The metadata labels `identifier` and `flow_run_id` will be replaced with a unique identifier for this run and the id of this Flow run respectively
- `image` will become the _registry_url/image_name:image_tag_ of your Flow's storage
- `command` and `args` will take the form of:

```bash
/bin/sh -c "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
```

- `env` will have some extra variables automatically appended to it for Cloud-based Flow runs:

```
PREFECT__CLOUD__GRAPHQL
PREFECT__CLOUD__API_KEY
PREFECT__CONTEXT__FLOW_RUN_ID
PREFECT__CONTEXT__NAMESPACE
PREFECT__CONTEXT__IMAGE
PREFECT__CONTEXT__FLOW_FILE_PATH
PREFECT__CLOUD__USE_LOCAL_SECRETS
PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS
PREFECT__CLOUD__SEND_FLOW_RUN_LOGS
PREFECT__LOGGING__EXTRA_LOGGERS
```

All other aspects of your Job will remain untouched. In some cases it is easiest to use a dummy first container similar to the YAML block above.

## Examples

#### Kubernetes Job Environment w/ Resource Requests & Limits

The following example will execute your Flow using the custom Job specification with user provided resource requests and limits.

The Job spec YAML is contained in a file called `job_spec.yaml` which should be placed in the same directory as the Flow and is loaded in your Environment with `job_spec_file="job_spec.yaml"`.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: my-prefect-job
  labels:
    identifier: ""
spec:
  template:
    metadata:
      labels:
        identifier: ""
    spec:
      restartPolicy: Never
      containers:
        - name: flow-container
          image: ""
          command: []
          args: []
          env:
            - name: MY_ENV
              value: foo
          resources:
            limits:
              cpu: "2"
              memory: 4G
            requests:
              cpu: "1"
              memory: 2G
```

```python
from prefect import task, Flow
from prefect.environments import KubernetesJobEnvironment
from prefect.storage import Docker


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Kubernetes Job Environment w/ Resource Requests & Limits",
    environment=KubernetesJobEnvironment(job_spec_file="job_spec.yaml"),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="k8s-job-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
