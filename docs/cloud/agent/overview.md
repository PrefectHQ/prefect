# Overview

The Prefect Agent is a small process that is spun up on supported platforms to orchestrate flow runs. The agent works by querying Prefect Cloud for new or incomplete flow runs and then allocating resources for them on the deployment's platform of choice.

Prefect Cloud is designed to follow a hybrid approach to workflow execution. This means that Prefect processes run inside tenant infrastructure and only send requests _out_ to Prefect Cloud. Both the Prefect Agent and all Prefect Flows which run using Cloud follow this communication pattern.

[[toc]]

### Agent Process

Agents start by first querying Prefect Cloud for their respective tenant ID (inferred from the API token that the agent is given). The agent will then periodically query Prefect Cloud for flow runs that need to be started on that agent's platform.

Flow runs can be created either through the [GraphQL API](../concepts/graphql.html), [CLI](../concepts/cli.html), [programatically](../concepts/flow_runs.html#creating-a-flow-run), or [UI](../concepts/ui.html). The agent scoped to the tenant which this flow run belongs to will then see that there us work which needs to be done. Metadata surrounding the flow run will be retrieved and used to create a unit of execution on the agent's platform. Examples of this could include a Docker container in the case of a Local Agent or a job in the case of a Kubernetes Agent.

Once the agent submits the flow run for execution, the agent returns to waiting for more flow runs to execute. That flow run that was submitted for execution is now set to a `Submitted` state.

### Installation

If you already have Prefect [installed](../../core/getting_started/installation.html) then there is no extra work needed to begin using Prefect Agents!

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

### Tokens

Prefect Agents rely on the use of a `RUNNER` token from Prefect Cloud. For information on tokens and how they are used visit the [Tokens](../concepts/tokens.html) page.

### Flow Affinity: Labels

Agents have an optional `labels` argument which allows for separation of execution when using multiple Agents. This is especially useful for teams who have various clusters running and they want different flows to run on specific clusters. For more information on labels and how to use them visit [Environments](../concepts/execution.html#labels).

By default Agents have no set labels and will therefore only pick up runs from flows which also have no specified Environment Labels. To set labels on your Agent they can be provided through a few methods:

- Initialization of the Agent class:

```python
from prefect.agent import LocalAgent

LocalAgent(labels=["dev", "staging"]).start()
```

- Arguments to the CLI:

```
$ prefect agent start --label dev --label staging
```

- As an environment variable:

```
$ export PREFECT__CLOUD__AGENT__LABELS='["dev", "staging"]'
```

:::tip Environment Variable
Setting labels through the `PREFECT__CLOUD__AGENT__LABELS` environment variable will make those labels the default unless overridden through initialization of an Agent class or through the CLI's `agent start` command.
:::
