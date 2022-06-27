# ECS Agent

The ECS Agent deploys flow runs as [AWS ECS Tasks](https://aws.amazon.com/ecs/)
on either EC2 or Fargate.

## Requirements

The required dependencies for the ECS Agent aren't [installed by
default](/core/getting_started/installation.md). If you're a `pip` user you'll
need to add the `aws` extra. Likewise, with `conda` you'll need to install
`boto3`:

Pip:

```bash
pip install prefect[aws]
```

Conda:

```bash
conda install -c conda-forge prefect boto3
```

!!! warning Prefect Server
    In order to use this agent with Prefect Server the server's GraphQL API
    endpoint must be accessible. This _may_ require changes to your Prefect Server
    deployment and/or [configuring the Prefect API
    address](./overview.md#prefect-api-address) on the agent.
:::

## Flow Configuration

The ECS Agent will deploy flows using either a
[UniversalRun](/orchestration/flow_config/run_configs.md#universalrun) (the
default) or [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun)
`run_config`. Using a `ECSRun` object lets you customize the deployment
environment for a flow (exposing `env`, `image`, `cpu`, etc...):

```python
from prefect.run_configs import ECSRun

# Configure extra environment variables for this flow,
# and set a custom image
flow.run_config = ECSRun(
    env={"SOME_VAR": "VALUE"},
    image="my-custom-image"
)
```

See the [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun)
documentation for more information.

## Agent Configuration

The ECS agent can be started from the Prefect CLI as

```bash
prefect agent ecs start
```

!!! tip API Keys <Badge text="Cloud"/>
    When using Prefect Cloud, this will require a service account API key, see
    [here](./overview.md#api_keys) for more information.
:::

Below we cover a few common configuration options, see the [CLI
docs](/api/latest/cli/agent.md#ecs-start) for a full list of options.

### AWS Credentials

The ECS Agent will need permissions to create task definitions and start tasks
in your ECS Cluster. You'll need to ensure it has the proper
[credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
(at least `aws_access_key_id`, `aws_secret_access_key`, and `region_name`).

[Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
(the library Prefect uses for AWS interaction) supports [a few different ways
of configuring this](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).
When possible we recommend using the `~/.aws/config` file, but
[environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables)
also work:

Config file:

```toml
# ~/.aws/config
[default]
aws_access_key_id=...
aws_secret_access_key=...
region=...
```

Environment Variables:

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=...
```

### Cluster

By default the agent will deploy flow run tasks into your default ECS cluster.
You can specify a different cluster using the `--cluster` option:

```bash
prefect agent ecs start --cluster my-cluster-arn
```

### Launch Type

The ECS agent can deploy flow runs on either Fargate (default) or EC2. You can
use the `--launch-type` option to configure this.

```bash
prefect agent ecs start --launch-type EC2
```

### Task Role ARN

ECS tasks use [task
roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
to provide additional permissions to tasks to make AWS API calls. You can configure a default task
role for tasks started by the agent using the `--task-role-arn` option:

```bash
prefect agent ecs start --task-role-arn my-task-role-arn
```

Flows can override this agent default by passing the `task_role_arn` option to
their respective [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun) `run_config`.

### Execution Role ARN

ECS tasks use [execution
roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)
to grant permissions to the ECS infrastructure to make AWS API calls on your
behalf. If actions taken to _start_ your task require external AWS services
(e.g. pulling an image from ECR), you'll need to configure an execution role.
Permissions used by your code once your task starts are granted via [task
roles](#task-role-arn) instead (see above).

ECS provides a builtin policy `AmazonECSTaskExecutionRolePolicy` that provides
common settings. This supports pulling images from ECR and enables using
CloudWatch logs. The full policy is below:

Execution Role Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

Agent Role Policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:CreateSecurityGroup",
                "ec2:CreateTags",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcs",
                "ec2:DeleteSecurityGroup",
                "ecs:CreateCluster",
                "ecs:DeleteCluster",
                "ecs:DeregisterTaskDefinition",
                "ecs:DescribeClusters",
                "ecs:DescribeTaskDefinition",
                "ecs:DescribeTasks",
                "ecs:ListAccountSettings",
                "ecs:ListClusters",
                "ecs:ListTaskDefinitions",
                "ecs:RegisterTaskDefinition",
                "ecs:RunTask",
                "ecs:StopTask",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:GetLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

Prefect Tasks Role Policy:
```
Depends on AWS API calls your Prefect tasks make. For example, if your Prefect task make calls to DynamoDB, you need to attach a policy with DynamoDB permissions to the task role, and provide this role to `task-role-arn` option in ECSRun config or prefect ecs agent.
```

Usually AWS will automatically create an IAM role with this policy named
`ecsTaskExecutionRole` (if not, you may need to create one yourself, see [the
AWS docs for more
info](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)).

You can configure a default execution role for tasks started by the agent using
the `--execution-role-arn` option:

```bash
prefect agent ecs start --execution-role-arn my-execution-role-arn
```

Flows can override this agent default by passing the `execution_role_arn` option to
their respective [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun) `run_config`.

### Custom Task Definition Template

For deeper customization of the Tasks created by the agent, you may want to
make use of a custom task definition template. This template can either be
configured per-flow (on the
[ECSRun](/orchestration/flow_config/run_configs.md#ecsrun) `run_config`), or on
the Agent as a default for flows that don't provide their own template.

The flow will be executed in a container named `flow` - if a container named
`flow` isn't part of the task definition template Prefect will add a new
container with that name (this allows adding sidecar containers without
requiring the user to define a `flow` container as well). Any option available to
[`register_task_definition`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition)
may be specified here. For reference, the default template packaged with
Prefect can be found
[here](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/ecs/task_definition.yaml).

To provide your own task definition template, you can use the `--task-definition` flag.
This takes a path to a job template YAML file. The path can be local to the agent,
or stored in cloud storage on S3.

```bash
# Using a local file
prefect agent ecs start --task-definition /path/to/my_definition.yaml

# Stored on S3
prefect agent ecs start --task-definition s3://bucket/path/to/my_definition.yaml
```

### Custom Runtime Options

Likewise, additional options to forward to
[`run_task`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task)
can be configured at the agent level using the `--run-task-kwargs` flag. This
option can also be provided at the flow level using the `run_task_kwargs`
keyword to [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun).

As with `--task-definition`, paths passed to `--run-task-kwargs` may be local
to the agent, or stored in cloud storage on S3.

```bash
# Using a local file
prefect agent ecs start --run-task-kwargs /path/to/options.yaml

# Stored on S3
prefect agent ecs start --run-task-kwargs s3://bucket/path/to/options.yaml
```

### Running ECS Agent in Production

An [`Amazon ECS service`](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html) enables creating long running task in your cluster. If any AWS task fails or stops for any reason, service scheduler launches a new instance of the task definition, which makes it great for running Prefect ECS Agent. 

For running agent as ECS service, you need to provide service definition parameters such as task definition, cluster name, service name, etc. You can create a service and provide those parameters using AWS console, or any Infrastructure as Code tools (Terraform, Pulumi, etc), or AWS CLI.

Let's see an example of creating a Fargate service type for Prefect Agent using AWS CLI. Assuming you have already created an ECS cluster in your VPC (you can use default cluster and VPC created by AWS), and have an API key for your Prefect agent, let's create a task definition for ECS Prefect agent using AWS CLI. Save the following task definition in `prefect-agent-td.json` file. Note, some values should be substituted with your API key and AWS account id.

```json
{
    "family": "prefect-agent",
    "requiresCompatibilities": ["FARGATE"],
    "networkMode": "awsvpc",
    "cpu": "512",
    "memory": "1024",
    "taskRoleArn": "arn:aws:iam::<>:role/prefectTaskRole",
    "executionRoleArn": "arn:aws:iam::<>:role/ecsTaskExecutionRole",
    "containerDefinitions": [
        {
            "name": "prefect-agent",
            "image": "prefecthq/prefect:0.14.13-python3.8",
            "essential": true,
            "command": ["prefect","agent","ecs","start"],
            "environment": [
                {
                    "name": "PREFECT__CLOUD__API_KEY",
                    "value": "<your-key>"
                },
                {
                    "name": "PREFECT__CLOUD__AGENT__LABELS",
                    "value": "['label1', 'label2']"},
                {
                    "name": "PREFECT__CLOUD__AGENT__LEVEL",
                    "value": "INFO"
                },
                {
                    "name": "PREFECT__CLOUD__API",
                    "value": "https://api.prefect.io"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/prefect-agent",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs",
                    "awslogs-create-group": "true"
                }
            }
        }
    ]
}
```

Register this task definition by running following command:

```bash
aws ecs register-task-definition --cli-input-json file://<full_path_to_task_definition_file>/prefect-agent-td.json
```

Finally, create a service from your task definition template:

```bash
aws ecs create-service 
    --service-name prefect-agent \
    --task-definition prefect-agent:1 \
    --desired-count 1 \
    --launch-type FARGATE \
    --platform-version LATEST \
    --cluster default \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-12344321],securityGroups=[sg-12344321],assignPublicIp=ENABLED}" \
    --tags key=key1,value=value1 key=key2,value=value2 key=key3,value=value3
```

Now, AWS service scheduler will create a task with running Prefect Agent, and you can check your logs in CloudWatch `/ecs/prefect-agent` log group.

### Throttling errors on flow submission

When using the ECS agent, you may encounter task definition registration limits based
on AWS API throttling and Service Quotas (formerly referred to as service limits). If
you encounter a registration limit due to AWS API throttling or Service Quotas, the
task definition fails to register and your flow will not run.

To learn more about AWS API throttling and Service Quotas see [Managing and monitoring API throttling in your workloads](https://aws.amazon.com/blogs/mt/managing-monitoring-api-throttling-in-workloads/)
on the AWS Management & Governance Blog.

AWS recommends employing retry logic when encountering AWS API rate limit and throttling
events.

When starting an ECS agent from the command line, you can configure retry behavior for
the ECS agent by setting [AWS CLI retry modes](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-retries.html).

For example, the following example specifies the AWS Adaptive retry mode and up to 10
retry attempts, then starts the ECS agent:

For example:

```bash
AWS_RETRY_MODE='adaptive' AWS_MAX_ATTEMPTS=10 prefect agent ecs start
```

If you are running the ECS agent in a container, set the environment variables in the
container definition.
