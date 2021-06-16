# Fargate Task Environment

::: warning
Flows configured with environments are being deprecated - we recommend users
transition to using "Run Configs" instead. See [flow
configuration](/orchestration/flow_config/overview.md) and [upgrading
tips](/orchestration/flow_config/upgrade.md) for more information.
:::

[[toc]]

## Overview

The Fargate Task Environment runs a Flow on a completely custom [Fargate Task](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html). This Environment is intended for use in cases where you want complete control over the Fargate Task your Flow runs on.

_For more information on the Fargate Task Environment visit the relevant [API documentation](/api/latest/environments/execution.html#fargatetaskenvironment)._

## Process

#### Initialization

The `FargateTaskEnvironment` has two groups of keyword arguments: boto3-related arguments and task-related arguments. All of this configuration revolves around how the [boto3]() library communicates with AWS. The design of this Environment is meant to be open to all access methodologies for AWS instead of adhering to a single mode of authentication.

This Environment accepts similar arguments to how boto3 authenticates with AWS: `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, and `region_name`. These arguments are directly passed to the [boto3 client]() which means you should initialize this Environment in the same way you would normally use boto3.

The other group of kwargs are those you would pass into boto3 for [registering](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition) a task definition and [running](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task) that task.

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

All of these kwargs will be loaded and stored upon initialization of the Environment. It will _never be sent to Prefect Cloud_ and will only exist inside your Flow's Docker storage object.

:::tip Task IAM Roles
Users have seen great performance in using [Task IAM Roles](https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-iam-roles.html) for their Flow execution.
:::

#### Setup

The Fargate Task Environment setup step is responsible for registering the Fargate Task if it does not already exist. First it checks for the existence of a task definition based on the `family` that was provided at initialization of this Environment. If the task definition is not found then it is created. This means that if a Flow is run multiple times the task definition will only need to be created once.

#### Execute

Create a new Fargate Task with the configuration provided at initialization of this Environment. That task is responsible for running your flow.

#### Task Spec Configuration

There are a few caveats to using the Fargate Task Environment that revolve around the provided boto3 kwargs. In the `containerDefinitions` that you provide, the **first container** listed will be the container that is used to run the Flow. This means that the first container will always be overridden during the `setup` step of this Environment.

```python
containerDefinitions=[
    {
        "name": "flow",
        "image": "image",
        "command": [],
        "environment": [],
        "essential": True,
    }
],
```

The container dictionary above will be changed during setup:

- `name` will become _flow-container_
- `image` will become the _registry_url/image_name:image_tag_ of your Flow's storage
- `command` will take the form of:

```python
[
    "/bin/sh",
    "-c",
    "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
]
```

- `environment` will have some extra variables automatically appended to it for Cloud-based Flow runs:

```
PREFECT__CLOUD__GRAPHQL
PREFECT__CLOUD__USE_LOCAL_SECRETS
PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS
PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS
PREFECT__CLOUD__SEND_FLOW_RUN_LOGS
PREFECT__LOGGING__EXTRA_LOGGERS
```

All other aspects of your `containerDefinitions` will remain untouched. In some cases it is easiest to use a dummy first container similar to the code block above.

During the execute step of your Environment the following container overrides will be set for boto3's `run_task`:

```
PREFECT__CLOUD__API_KEY
PREFECT__CONTEXT__FLOW_RUN_ID
PREFECT__CONTEXT__IMAGE
PREFECT__CONTEXT__FLOW_FILE_PATH
```

## Examples

#### Fargate Task Environment w/ Resources

The following example will execute your Flow using the Fargate Task Environment with the provided Task specification taking advantage of resource requests. This example also makes use of an `aws_session_token` and [IAM Role for task execution](https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-iam-roles.html).

```python
from prefect import task, Flow
from prefect.environments import FargateTaskEnvironment
from prefect.storage import Docker


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Fargate Task Environment",
    environment=FargateTaskEnvironment(
        launch_type="FARGATE",
        aws_session_token="MY_AWS_SESSION_TOKEN",
        region="us-east-1",
        cpu="256",
        memory="512",
        networkConfiguration={
            "awsvpcConfiguration": {
                "assignPublicIp": "ENABLED",
                "subnets": ["MY_SUBNET_ID"],
                "securityGroups": ["MY_SECURITY_GROUP"],
            }
        },
        family="my_flow",
        taskDefinition="my_flow",
        taskRoleArn="MY_TASK_ROLE_ARN",
        executionRoleArn="MY_EXECUTION_ROLE_ARN",
        containerDefinitions=[{
            "name": "flow-container",
            "image": "image",
            "command": [],
            "environment": [],
            "essential": True,
        }]
    ),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="fargate-task-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
