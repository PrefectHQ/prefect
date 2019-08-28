# Overview

The Prefect Agent is a small process that is spun up on supported platforms to orchestrate flow runs. The agent works by querying Prefect Cloud for new or incomplete flow runs and then allocating resources for them on the deployment's platform of choice.

Prefect Cloud is designed to follow a hybrid approach to workflow execution. This means that Prefect processes run inside tenant infrastructure and only send requests _out_ to Prefect Cloud. Both the Prefect Agent and all Prefect Flows which run using Cloud follow this communication pattern. 

### Agent Process

Agents start by first querying Prefect Cloud for their respective tenant ID (inferred from the API token that the agent is given). The agent will then periodically query Prefect Cloud for flow runs that need to be started on that agent's platform.

Flow runs can be created either through the [GraphQL API](https://docs.prefect.io/cloud/cloud_concepts/graphql.html), [CLI](https://docs.prefect.io/cloud/cloud_concepts/cli.html), [programatically](https://docs.prefect.io/cloud/cloud_concepts/flow_runs.html#creating-a-flow-run), or [UI](https://docs.prefect.io/cloud/cloud_concepts/ui.html). The agent scoped to the tenant which this flow run belongs to will then see that there us work which needs to be done. Metadata surrounding the flow run will be retrieved and used to create a unit of execution on the agent's platform. Examples of this could include a Docker container in the case of a Local Agent or a job in the case of a Kubernetes Agent.

Once the agent submits the flow run for execution, the agent returns to waiting for more flow runs to execute. That flow run that was submitted for execution is now set to a `Submitted` state.

### Installation

If you already have Prefect [installed](https://docs.prefect.io/guide/getting_started/installation.html) then there is no extra work needed to begin using Prefect Agents!

### Usage

Prefect Agents can easily be configured through the CLI.

```
$ prefect agent
Usage: prefect agent [OPTIONS] COMMAND [ARGS]...

  Manage Prefect agents.

  Usage:
      $ prefect agent [COMMAND]

  Arguments:
      start       Start a Prefect agent
      install     Output platform-specific agent installation configs

  Examples:
      $ prefect agent start
      ...agent begins running in process...

      $ prefect agent start kubernetes --token MY_TOKEN
      ...agent begins running in process...

      $ prefect agent install --token MY_TOKEN --namespace metrics
      ...k8s yaml output...

Options:
  -h, --help  Show this message and exit.
```

All Prefect Agents are also extendable as Python objects and can be used programatically!

```python
from prefect.agent import LocalAgent

LocalAgent().start()
```
