# Overview

The Prefect agent is a small process spun up to orchestrate flow runs. The agent queries the Prefect API for new or incomplete flow runs and allocates resources for them on the deployment's platform of choice.

If using the Prefect Cloud API, it's important to note that Prefect Cloud uses a hybrid approach to workflow execution. This means that Prefect processes run inside the tenant's infrastructure and only send requests _out_ to Prefect Cloud. Both the Prefect agent and all Prefect flows which run using Cloud follow this communication pattern.

[[toc]]

### Agent Process

Agents start by first querying the Prefect API for their respective tenant ID (inferred from the API token that the agent is given). The agent then continually queries the Prefect API for flow runs to be started on that agent's platform.

Flow runs can be created either through the [GraphQL API](../concepts/graphql.html), [CLI](../concepts/cli.html), [programatically](../concepts/flow_runs.html#creating-a-flow-run), or [UI](../concepts/ui.html). The agent scoped to the tenant to which this flow run belongs will then see that there is work which needs to be done. Metadata surrounding the flow run will be retrieved and used to create a unit of execution on the agent's platform. Examples of this could include a Docker container in the case of a Docker agent or a job in the case of a Kubernetes agent.

Once the agent submits the flow run for execution, the agent returns to waiting for more flow runs to execute. That flow run that was submitted for execution is now set to a `Submitted` state. The `Submitted` state will contain information regarding identification of the deployment.

If for any reason the agent encounters an issue deploying the flow run for execution then it will mark that flow run as `Failed` with the message set to the error it encountered.

### Installation

If Prefect is already [installed](../../core/getting_started/installation.html) no additional work is required to begin using Prefect agents!

### Usage

Prefect agents can easily be configured through the CLI.

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

      $ prefect agent install kubernetes --token MY_TOKEN --namespace metrics
      ...k8s yaml output...

Options:
  -h, --help  Show this message and exit.
```

All Prefect Agents are also extendable as Python objects and can be used programatically!

```python
from prefect.agent import DockerAgent

DockerAgent().start()
```

### Tokens <Badge text="Cloud"/>

Prefect agents rely on the use of a `RUNNER` token from Prefect Cloud. For information on tokens and how they are used visit the [Tokens](../concepts/tokens.html) page.

### Flow Affinity: Labels

Agents have an optional `labels` argument which allows for separation of execution when using multiple agents. This is especially useful for teams wanting to run specific flows on different clusters. For more information on labels and how to use them visit [Environments](../execution/overview.html#labels).

By default, agents have no set labels and will only pick up runs from flows with no specified Environment Labels. Labels can be provided to an agent through a few methods:

- Initialization of the Agent class:

```python
from prefect.agent import DockerAgent

DockerAgent(labels=["dev", "staging"]).start()
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

### Health Checks

Agents can optionally run a private HTTP server for use as a health check.
Health checks can be used by common orchestration services (e.g.
``supervisord``, ``docker``, ``kubernetes``, ...) to check that the agent is
running properly and take actions (such as restarting the agent) if it's not.

A few ways to enable:

- Passing an argument to the CLI:

```
$ prefect agent start --agent-address http://localhost:8080
```

- Setting an environment variable:

```
$ export PREFECT__CLOUD__AGENT__AGENT_ADDRESS=http://localhost:8080
```

- Setting ``cloud.agent.agent_address`` in your [configuration](../../core/concepts/configuration.html):

If enabled, the HTTP health check will be available via the ``/api/health``
route at the configured agent address. This route returns ``200 OK`` if the
agent is running and health, and will error otherwise.
