# Vertex Agent

The Vertex Agent executes flow runs as [Vertex Custom Jobs](https://cloud.google.com/vertex-ai/docs/training/create-custom-job).
Vertex describes these as "training" jobs, but they can be used to run any kind of flow.

## Requirements

The required dependencies for the Vertex Agent aren't [installed by
default](/core/getting_started/installation.md). You'll
need to add the `gcp` extra via `pip`. 

```bash
pip install prefect[gcp]
```

!!! warning Prefect Server
    In order to use this agent with Prefect Server the server's GraphQL API
    endpoint must be accessible. This _may_ require changes to your Prefect Server
    deployment and/or [configuring the Prefect API
    address](./overview.md#prefect-api-address) on the agent.


## Flow Configuration

The Vertex Agent will deploy flows using either a
[UniversalRun](/orchestration/flow_config/run_configs.md#universalrun) (the
default) or [VertexRun](/orchestration/flow_config/run_configs.md#vertexrun)
`run_config`. Using a `VertexRun` object lets you customize the deployment
environment for a flow (exposing `env`, `image`, `machine_type`, etc...):

```python
from prefect.run_configs import VertexRun

# Configure extra environment variables for this flow,
# and set a custom image and machine type
flow.run_config = VertexRun(
    env={"SOME_VAR": "VALUE"},
    image="my-custom-image",
    machine_type="e2-highmem-16",
)
```

See the [VertexRun](/orchestration/flow_config/run_configs.md#vertexrun)
documentation for more information.

## Agent Configuration

The Vertex agent can be started from the Prefect CLI as

```bash
prefect agent vertex start
```

!!! tip API Keys <Badge text="Cloud"/>
    When using Prefect Cloud, this will require a service account API key, see
    [here](./overview.md#api_keys) for more information.


Below we cover a few common configuration options, see the [CLI
docs](/api/latest/cli/agent.md#vertex-start) for a full list of options.

### Project

By default the agent will deploy flow run tasks into the current project (as defined by [google.auth.default](https://google-auth.readthedocs.io/en/latest/reference/google.auth.html))
You can specify a different project using the `--project` option:

```bash
prefect agent vertex start --project my-project
```

This can be a different project than the agent is running in, as long as the account has permissions
to start Vertex Custom Jobs in the specified project.

### Region

Vertex requires a region in which to run the flow, and will default to `us-central1`
You can specify a different region using the `--region-name` option:

```bash
prefect agent vertex start --region-name us-east1
```

### Service Account

Vertex jobs can run as a specified service account. Vertex provides a default, but specifying a specific
account can give you more control over what resources the flow runs are allowed to access.
You can specify a non-default account using the `--service-account` option:

```bash
prefect agent vertex start --service-account my-account@my-project.iam.gserviceaccount.com
```

