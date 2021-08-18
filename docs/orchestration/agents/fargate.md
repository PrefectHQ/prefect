# Fargate Agent (Deprecated)

::: warning
The Fargate Agent is deprecated, we recommend users transition to using the new
[ECS Agent](/orchestration/agents/ecs.md) instead. Note that the ECS agent only
supports [RunConfig](/orchestration/flow_config/overview.md#run-configuration)
based flows. Flows using the legacy `Environment` classes will need to be
transitioned before moving off the fargate agent.
:::

The Fargate Agent is an agent designed to deploy flows as Tasks using AWS Fargate. This agent can be run anywhere so long as the proper AWS configuration credentials are provided.

[[toc]]

::: warning Core server
In order to use this agent with Prefect Core's server the server's GraphQL API endpoint must be accessible.
:::

### Requirements

When running the Fargate you may optionally provide `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` (specific to temporary credentials). If these three items are not explicitly defined, boto3 will default to environment variables or your credentials file. Having the `REGION_NAME` defined along with the appropriate credentials stored per aws expectations are required to initialize the [boto3 client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#client). For more information on properly setting your credentials, check out the boto3 documentation [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).

### Usage

```
$ prefect agent fargate start

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-08-27 14:33:39,772 - agent - INFO - Starting FargateAgent
2019-08-27 14:33:39,772 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/orchestration/
2019-08-27 14:33:40,932 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-08-27 14:33:40,932 - agent - INFO - Waiting for flow runs...
```

The Fargate Agent can be started either through the Prefect CLI or by importing the `FargateAgent` class from the core library. Starting the agent from the CLI will require that the required AWS configuration arguments are set at the environment level while importing the agent class in a Python process will allow you to specify them at initialization.

::: tip API Keys <Badge text="Cloud"/>
You can specify a service account API key via the CLI with

```bash
$ prefect agent fargate start -k SERVICE_ACCOUNT_API_KEY
```

For additional methods of specifying API keys, see the [API key documentation](../concepts/api_keys.md).
:::

### Installation

Unlike the Kubernetes Agent, the Fargate Agent is not generally installed to run on Fargate itself and instead it can be spun up anywhere with the correct variables set.

Through the Prefect CLI:

```
$ export AWS_ACCESS_KEY_ID=MY_ACCESS
$ export AWS_SECRET_ACCESS_KEY=MY_SECRET
$ export AWS_SESSION_TOKEN=MY_SESSION
$ export REGION_NAME=MY_REGION
$ prefect agent fargate start
```

In a Python process:

```python
from prefect.agent.fargate import FargateAgent

agent = FargateAgent(
        aws_access_key_id="MY_ACCESS",
        aws_secret_access_key="MY_SECRET",
        aws_session_token="MY_SESSION",
        region_name="MY_REGION",
        )

agent.start()
```

You are now ready to run some flows!

### Process

The Fargate Agent periodically polls for new flow runs to execute. When a flow run is retrieved from Prefect Cloud the agent checks to make sure that the flow was registered with a Docker storage option. If so, the agent then creates a Task using the `storage` attribute of that flow, and runs `prefect execute flow-run`.

If it is the first run of a particular flow then a Task Definition will be registered. Each new run of that flow will run using that same Task Definition and it will override some of the environment variables in order to specify which flow run is occurring.

When the flow run is found and the Task is run the logs of the agent should reflect that:

```
2019-09-01 19:00:30,532 - agent - INFO - Starting FargateAgent
2019-09-01 19:00:30,533 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/orchestration/
2019-09-01 19:00:30,655 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-09-01 19:00:30,733 - agent - INFO - Waiting for flow runs...
2019-09-01 19:01:08,835 - agent - INFO - Found 1 flow run(s) to submit for execution.
2019-09-01 19:01:09,158 - agent - INFO - Submitted 1 flow run(s) for execution.
```

The Fargate Task run should be created and it will start in a `PENDING` state. Once the resources are provisioned it will enter a `RUNNING` state and on completion it will finish as `COMPLETED`.

### Configuration

The Fargate Agent allows for a set of AWS configuration options to be set or provided in order to initialize the boto3 client. All of these options can be provided at initialization of the `FargateAgent` class or through an environment variable:

- aws_access_key_id (str, optional): AWS access key id for connecting the boto3 client. Defaults to the value set in the environment variable `AWS_ACCESS_KEY_ID`.
- aws_secret_access_key (str, optional): AWS secret access key for connecting the boto3 client. Defaults to the value set in the environment variable `AWS_SECRET_ACCESS_KEY`.
- aws_session_token (str, optional): AWS session key for connecting the boto3 client. Defaults to the value set in the environment variable `AWS_SESSION_TOKEN`.
- region_name (str, optional): AWS region name for connecting the boto3 client. Defaults to the value set in the environment variable `REGION_NAME`.
- botocore_config (dict, optional): [botocore configuration](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html) options to be passed to the boto3 client.

- enable_task_revisions (bool, optional): Enable registration of task definitions using revisions.
  When enabled, task definitions will use flow name as opposed to flow id and each new version will be a
  task definition revision. Each revision will be registered with a tag called `PrefectFlowId`
  and `PrefectFlowVersion` to enable proper lookup for existing revisions. Flow name is reformatted
  to support task definition naming rules by converting all non-alphanumeric characters to '\*'.
  Defaults to False.
- use_external_kwargs (bool, optional): When enabled, the agent will check for the existence of an
  external json file containing kwargs to pass into the run_flow process.
  Defaults to False.
- external_kwargs_s3_bucket (str, optional): S3 bucket containing external kwargs.
- external_kwargs_s3_key (str, optional): S3 key prefix for the location of `<slugified_flow_name>/<flow_id[:8]>.json`.
- \*\*kwargs (dict, optional): additional keyword arguments to pass to boto3 for
  `register_task_definition` and `run_task`

While the above configuration options allow for the initialization of the boto3 client, you may also need to specify the arguments that allow for the registering and running of Fargate task definitions. The Fargate Agent makes no assumptions on how your particular AWS configuration is set up and instead has a `kwargs` argument which will accept any arguments for boto3's `register_task_definition` and `run_task` functions.

::: tip Validating Configuration
The Fargate Agent has a utility function [`validate_configuration`](/api/latest/agent/fargate.html#fargateagent) which can be used to test the configuration options set on the agent to ensure is it able to register the task definition and run the task.
:::

Accepted kwargs for [`register_task_definition`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition):

```
taskRoleArn                 string
executionRoleArn            string
networkMode                 string
volumes                     list
placementConstraints        list
cpu                         string
memory                      string
tags                        list
pidMode                     string
ipcMode                     string
proxyConfiguration          dict
inferenceAccelerators       list
```

We have also added the ability to select items to the `containerDefinitions` kwarg of `register_task_definition`:

```
environments               list
secrets                    list
mountPoints                list
logConfiguration           dict
repositoryCredentials      dict
```

Environment was added to support adding flow level environment variables via the `use_external_kwargs` described later on in the documentation.
You should continue to use the `env_vars` kwarg to pass agent level environment variables to your tasks.

This adds support for Native AWS Secrets Manager and/or Parameter Store in your flows.

Given that you running your Fargate tasks on `platformVersion` 1.4.0 or higher, you can also leverage `volumes` and `mountPoints` to attach an EFS backed volume on to your tasks.
In order to use `mountPoints` you will need to include the proper `volumes` kwarg as shown below.

Here is an example of what kwargs would look like with `containerDefinitions` via Python:

```python
from prefect.agent.fargate import FargateAgent

agent = FargateAgent(
    launch_type="FARGATE",
    aws_access_key_id="MY_ACCESS",
    aws_secret_access_key="MY_SECRET",
    aws_session_token="MY_SESSION",
    region_name="MY_REGION",
    networkConfiguration={
        "awsvpcConfiguration": {
            "assignPublicIp": "ENABLED",
            "subnets": ["my_subnet_id"],
            "securityGroups": []
        }
    },
    cpu="256",
    memory="512",
    platformVersion="1.4.0",
    containerDefinitions=[{
        "environment": [{
            "name": "TEST_ENV",
            "value": "Success!"
        }],
        "secrets": [{
            "name": "TEST_SECRET",
            "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test"
        }],
        "mountPoints": [{
            "sourceVolume": "myEfsVolume",
            "containerPath": "/data",
            "readOnly": False
        }],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": "/my/log/group",
                "awslogs-region": "us-east-1",
                "awslogs-stream-prefix": "prefect-flow-runs",
                "awslogs-create-group": "true",
            },
        },
    }],
    volumes=[
        {
          "name": "myEfsVolume",
          "efsVolumeConfiguration": {
            "fileSystemId": "my_efs_id",
            "transitEncryption": "ENABLED",
            "authorizationConfig": {
                "accessPointId": "my_efs_access_point",
                "iam": "ENABLED"
            }
          }
        }
      ]
    ),

agent.start()
```

You can also pass these in using environment variables with the format of `containerDefinitions_<key>`, for example:

```
containerDefinitions_environment
containerDefinitions_secrets
containerDefinitions_mountPoints
```

Accepted kwargs for [`run_task`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task):

```
cluster                     string
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

:::tip boto3 kwargs
For more information on using Fargate with boto3 and to see the list of supported configuration options please visit the [relevant API documentation.](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html) Most importantly the functions [register_task_definition()](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition)and [run_task()](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task).
:::

All of these options can be provided at initialization of the `FargateAgent` class or through an environment variable. This means that the environment variables will need to be string representations of the values they represent.

For example, the `networkConfiguration` kwarg accepts a dictionary and if provided through an environment variable it will need to be a string representation of that dictionary.

```python
networkConfiguration={
    "awsvpcConfiguration": {
        "assignPublicIp": "ENABLED",
        "subnets": ["my_subnet_id"],
        "securityGroups": []
    }
}
```

```bash
networkConfiguration="{'awsvpcConfiguration': {'assignPublicIp': 'ENABLED', 'subnets': ['my_subnet_id'], 'securityGroups': []}}"
```

:::warning Case Sensitive Environment Variables
Please note that when setting the boto3 configuration for the `register_task_definition` and `run_task` the keys are case sensitive. For example: if setting placement constraints through an environment variable it must match boto3's case sensitive `placementConstraints`.
:::

#### External Kwargs

By default, all of the kwargs mentioned above are passed in to the Agent configuration, which means that every flow inherits from them. There are use cases where you will want to use different attributes for different flows and that is supported through enabling `use_external_kwargs`.

When enabled, the Agent will check for the existence of an external kwargs file from a bucket in S3. In order to use this feature you must also provide `external_kwargs_s3_bucket` and `external_kwargs_s3_key` to your Agent. If a file exists matching a set S3 key path, the Agent will apply these kwargs to the boto3 `register_task_definition` and `run_task` functions.

External kwargs must be in `json` format.

The S3 key path that will be used when fetching files is:

```
<external_kwargs_s3_key>/slugified_flow_name>/<flow_id[:8]>.json
```

For example if the `external_kwargs_s3_key` is `prefect`, the flow name is `flow #1` and the flow ID is `a718df81-3376-4039-a1e6-cf5b79baa7d4` then your full s3 key path will be:

```
prefect/flow-1/a718df81.json
```

Below is an example S3 key patching to a particular flow:

```python
import os
from slugify import slugify

flow_id = flow.register(project_name="<YOUR_PROJECT>")
s3_key = os.path.join('prefect-artifacts', slugify(flow.name), '{}.json'.format(flow_id[:8]))
```

This functionality requires the agent have a proper IAM policy for fetching objects from S3, here is an example:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowListWorkBucket",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetBucketAcl"
            ],
            "Resource": "<s3 bucket root>"
        },
        {
            "Sid": "AllowGetPutDeleteWorkObject",
            "Effect": "Allow",
            "Action": [
                "s3:GetObjectVersion",
                "s3:GetObject"
            ],
            "Resource": "<s3 bucket kwargs path>"
        }
    ]
}
```

External kwargs also support `containerDefinitions` mentioned above, which makes it easier support different environment variables, secrets, and mounted EFS volumes for different flows.

Here is an example of the external kwargs json:

```json
{
    "networkConfiguration": {
        "awsvpcConfiguration": {
            "assignPublicIp": "ENABLED",
            "subnets": ["my_subnet_id"],
            "securityGroups": []
        }
    },
    "cpu": "256",
    "memory"": "512",
    "platformVersion": "1.4.0",
    "containerDefinitions": [{
        "environment": [{
            "name": "TEST_ENV",
            "value": "Success!"
        }],
        "secrets": [{
            "name": "TEST_SECRET",
            "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test"
        }],
        "mountPoints": [{
            "sourceVolume": "myEfsVolume",
            "containerPath": "/data",
            "readOnly": false
        }]
    }],
    "volumes": [
        {
          "name": "myEfsVolume",
          "efsVolumeConfiguration": {
            "fileSystemId": "my_efs_id",
            "transitEncryption": "ENABLED",
            "authorizationConfig": {
                "accessPointId": "my_efs_access_point",
                "iam": "ENABLED"
        }
      }
    }
  ]
}
```

#### Task Revisions

By default, a new task definition is created each time there is a new flow version executed. However, ECS does offer the ability to apply changes through the use of revisions. The `enable_task_revisions` flag will enable using revisions by doing the following:

- Use a slugified flow name for the task definition family name.
  For example, `flow #1` becomes `flow-1`.
- Add a tag called `PrefectFlowId` and `PrefectFlowVersion` to enable proper lookup for existing revisions.

This means that for each flow, the proper task definition, based on flow ID and version, will be used. If a new flow version is run, a new revision is added to the flow's task definition family. Your task definitions will now have this hierarchy:

```
<flow name>
  - <flow name>:<revision number>
  - <flow name>:<revision number>
  - <flow name>:<revision number>
```

This functionality requires the agent have a proper IAM policy for creating task definition revisions and using the resource tagging API. Here is an example IAM policy:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ResourceAllItems",
            "Effect": "Allow",
            "Action": [
                "tag:Get*",
                "logs:PutLogEvents",
                "logs:CreateLogStream",
                "logs:CreateLogGroup",
                "events:PutTargets",
                "events:PutRule",
                "events:DescribeRule",
                "ecs:StopTask",
                "ecs:RegisterTaskDefinition",
                "ecs:Describe*",
                "ecr:GetDownloadUrlForLayer",
                "ecr:GetAuthorizationToken",
                "ecr:BatchGetImage",
                "ecr:BatchCheckLayerAvailability",
                "ec2:DescribeSubnets"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EcsTaskRun",
            "Effect": "Allow",
            "Action": "ecs:RunTask",
            "Resource": "arn:aws:ecs:<region>:<account_id>:task-definition/*",
            "Condition": {
                "ForAllValues:StringEquals": {
                    "aws:TagKeys": [
                        "PrefectFlowVersion",
                        "PrefectFlowId"
                    ]
                }
            }
        },
        {
            "Sid": "IamPassRole",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "*"
        }
    ]
}
```

### Configuration Examples

Below are two minimal examples which specify information for connecting to boto3 as well as the task's resource requests and network configuration. The first example initializes a `FargateAgent` with kwargs passed in and the second example uses the Prefect CLI to start the Fargate Agent with kwargs being loaded from environment variables.

#### Python Script

```python
from prefect.agent.fargate import FargateAgent

agent = FargateAgent(
    aws_access_key_id="...",
    aws_secret_access_key="...",
    region_name="us-east-1",
    cpu="256",
    memory="512",
    networkConfiguration={
        "awsvpcConfiguration": {
            "assignPublicIp": "ENABLED",
            "subnets": ["my_subnet_id"],
            "securityGroups": []
        }
    }
)

agent.start()
```

#### Prefect CLI

```bash
$ export AWS_ACCESS_KEY_ID=...
$ export AWS_SECRET_ACCESS_KEY=...
$ export REGION_NAME=us-east-1
$ export cpu=256
$ export memory=512
$ export networkConfiguration="{'awsvpcConfiguration': {'assignPublicIp': 'ENABLED', 'subnets': ['my_subnet_id'], 'securityGroups': []}}"

$ prefect agent fargate start
```

:::warning Outbound Traffic
If you encounter issues with Fargate raising errors in cases of client timeouts or inability to pull containers then you may need to adjust your `networkConfiguration`. Visit [this discussion thread](https://github.com/aws/amazon-ecs-agent/issues/1128#issuecomment-351545461) for more information on configuring AWS security groups.
:::

#### Prefect CLI Using Kwargs

All configuration options for the Fargate Agent can also be provided to the `prefect agent fargate start` CLI command. They must match the camel casing used by boto3 but both the single kwarg as well as with the standard prefix of `--` are accepted. This means that `taskRoleArn=""` is the same as `--taskRoleArn=""`.

```bash
$ export AWS_ACCESS_KEY_ID=...
$ export AWS_SECRET_ACCESS_KEY=...
$ export REGION_NAME=us-east-1

$ prefect agent fargate start cpu=256 memory=512 networkConfiguration="{'awsvpcConfiguration': {'assignPublicIp': 'ENABLED', 'subnets': ['my_subnet_id'], 'securityGroups': []}}"
```

Kwarg values can also be provided through environment variables. This is useful in situations where case sensitive environment variables are desired or when using templating tools like Terraform to deploy your Agent.

```bash
$ export AWS_ACCESS_KEY_ID=...
$ export AWS_SECRET_ACCESS_KEY=...
$ export REGION_NAME=us-east-1
$ export CPU=256
$ export MEMORY=512
$ export NETWORK_CONFIGURATION="{'awsvpcConfiguration': {'assignPublicIp': 'ENABLED', 'subnets': ['my_subnet_id'], 'securityGroups': []}}"

$ prefect agent fargate start cpu=$CPU memory=$MEMORY networkConfiguration=$NETWORK_CONFIGURATION
```
