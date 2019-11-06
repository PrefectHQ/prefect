# Fargate Task Environment

[[toc]]

## Overview

The Fargate Task Environment is an environment that runs a Flow on a completely custom [Fargate Task](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html). This environment is intended for use in cases where users want complete control over the Fargate Task their Flow runs on.

*For more information on the Fargate Task Environment visit the relevant [API documentation](/api/unreleased/environments/execution.html#fargatetaskenvironment).*

## Process

#### Initialization

The `FargateTaskEnvironment` has two groups of keyword arguments. All of this configuration revolves around how the [boto3]() library communicates with AWS. The design of this Environment is meant to be open to all access methodologies for AWS instead of adhering to a single mode of authentication.

This Environment accepts similar arguments to how boto3 authenticates with AWS: `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, and `region_name`. These arguments are directly passed to the [boto3 client]() which means you should initialize this environment in that same way you would normally use boto3.

After specifying credentials for the boto3 client the other group of kwargs falls into the category of any arguments you would pass into boto3 for [registering](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition) a task definition and [running](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task) that task.

Accepted kwargs for [`register_task_definition`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition):

```
family                      string
taskRoleArn                 string
executionRoleArn            string
networkMode                 string
containerDefinitions        list
volumes                     list
placementConstraints        list
requiresCompatibilities     list
cpu                         string
memory                      string
tags                        list
pidMode                     string
ipcMode                     string
proxyConfiguration          dict
inferenceAccelerators       list
```

Accepted kwargs for [`run_task`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task):

```
cluster                     string
taskDefinition              string
count                       integer
startedBy                   string
group                       string
placementConstraints        list
placementStrategy           list
platformVersion             string
networkConfiguration        dict
tags                        list
enableECSManagedTags        boolean
propagateTags               string
```

On initialization all of these kwargs will be loaded and stored on the environment. It will never be sent to Prefect Cloud and will only exist inside your Flow's Docker storage.

:::tip Task IAM Roles
Users have seen great performance in using [Task IAM Roles](https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-iam-roles.html) for their Flow execution.
:::

#### Setup

The Fargate Task Environment setup step

#### Execute

Create a new [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) with the configuration provided at initialization of this environment. That Job is responsible for running the Flow.

#### Job Spec Configuration

There are a few caveats to using the Kubernetes Job Environment that revolve around the format of the provided Job YAML. In the Job specification that you provide the **first container** listed will be the container that is used to run the Flow. This means that the first container will always be overridden during the `execute` step of this Environment.

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

In the above YAML block `flow-container` will have a few aspects changed during execution.

- The metadata labels `identifier` and `flow_run_id` will be replaced with a unique identifier for this run and the id of this Flow run respectively
- `image` will become the *registry_url/image_name:image_tag* of your Flow's storage
- `command` and `args` will take the form of:

```bash
/bin/sh -c 'python -c "from prefect.environments import KubernetesJobEnvironment; KubernetesJobEnvironment().run_flow()"'
```

- `env` will have some extra variables automatically appended to it for Cloud-based Flow runs:

```
PREFECT__CLOUD__GRAPHQL
PREFECT__CLOUD__AUTH_TOKEN
PREFECT__CONTEXT__FLOW_RUN_ID
PREFECT__CONTEXT__NAMESPACE
PREFECT__CONTEXT__IMAGE
PREFECT__CONTEXT__FLOW_FILE_PATH
PREFECT__CLOUD__USE_LOCAL_SECRETS
PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS
PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS
PREFECT__LOGGING__LOG_TO_CLOUD
```

All other aspects of your Job will remain untouched. In some cases it is easiest to simply use a dummy first container similar to the YAML block above.

## Examples

#### Kubernetes Job Environment w/ Resource Requests & Limits

The following example will execute your Flow using the custom Job specification with user provided resource requests and limits.

The Job spec YAML is contained in a file called `job_spec.yaml` which exists in the same directory as the Flow and it is loaded on our environment with `job_spec_file="job_spec.yaml"`.

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
from prefect.environments.storage import Docker


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
        registry_url="joshmeek18", image_name="flows"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
