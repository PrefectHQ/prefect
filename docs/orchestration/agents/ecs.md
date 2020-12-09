# ECS Agent

The ECS Agent deploys flow runs as [AWS ECS Tasks](https://aws.amazon.com/ecs/)
on either EC2 or Fargate.

## Requirements

The required dependencies for the ECS Agent aren't [installed by
default](/core/getting_started/installation.md). If you're a `pip` user you'll
need to add the `aws` extra. Likewise, with `conda` you'll need to install
`boto3`:

:::: tabs Installing Extra AWS Requirements
::: tab Pip
```bash
pip install prefect[aws]
```
:::
::: tab Conda
```bash
conda install -c conda-forge prefect boto3
```
:::
::::

::: warning Prefect Server
In order to use this agent with Prefect Server the server's GraphQL API
endpoint must be accessible. This *may* require changes to your Prefect Server
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

::: tip Tokens <Badge text="Cloud"/>
When using Prefect Cloud, this will require a `RUNNER` API token, see
[here](./overview.md#tokens) for more information.
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

:::: tabs Example boto3 configuration
::: Config file
```toml
[default]
aws_access_key_id=...
aws_secret_access_key=...
region=...
```
:::
::: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=...
```
:::
::::

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
to provide additional permissions to tasks. You can configure a default task
role for tasks started by the agent using the `--task-role-arn` option:

```bash
prefect agent ecs start --task-role-arn my-task-role-arn
```

Flows can override this agent default by passing the `task_role_arn` option to
their respective [ECSRun](/orchestration/flow_config/run_configs.md#ecsrun) `run_config`.

### Custom Task Definition Template

For deeper customization of the Tasks created by the agent, you may want to
make use of a custom task definition template. This template can either be
configured per-flow (on the
[ECSRun](/orchestration/flow_config/run_configs.md#ecsrun) `run_config`), or on
the Agent as a default for flows that don't provide their own template.

Any option available to
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
