# Local Agent

The local agent starts flow runs as processes local to the same machine it is
running on. It's useful for running lightweight workflows on standalone
machines, testing flows locally, or quickly getting acclimated with the Prefect
API. While the local agent is fully capable of executing flows in conjunction
with the Prefect API, we generally recommend using one of the other agents to
help with modularity and scale.

[[toc]]

## Requirements

The local agent has no outside dependencies and only requires that [Prefect is installed](/core/getting_started/installation.md).

If you want to use a Prefect backend for orchestrating and managing flows, you can use Prefect Cloud or the open-source Prefect Server.

To learn more about Prefect Cloud, which is the recommended orchestration backend, see the [Orchestration layer set up](/orchestration/getting-started/set-up.html) documentation.

To learn more about Prefect Server, see the [Server Overview](/orchestration/server/overview.html) documentation and the instructions for [Deploying to a single node](/orchestration/server/deploy-local.html).

!!! tip Docker
    If running the local agent inside a Docker container, we recommend you also use
    an init process like [`tini`](https://github.com/krallin/tini). Running without
    an init process may result in lingering zombie processes accumulating in your
    container. If you're using the [official Prefect docker
    images](https://hub.docker.com/r/prefecthq/prefect) then this is already
    handled for you.
:::

## Flow Configuration

The Local Agent will deploy flows using either a
[UniversalRun](/orchestration/flow_config/run_configs.md#universalrun) (the
default) or [LocalRun](/orchestration/flow_config/run_configs.md#localrun)
`run_config`. Using a `LocalRun` object lets you customize the deployment
environment for a flow (exposing `env`, `working_dir`, etc...):

```python
from prefect.run_configs import LocalRun

# Configure extra environment variables for this flow,
# and set a custom working directory
flow.run_config = LocalRun(
    env={"SOME_VAR": "VALUE"},
    working_dir="/path/to/working-directory"
)
```

See the [LocalRun](/orchestration/flow_config/run_configs.md#localrun)
documentation for more information.

## Agent Configuration

The local agent can be started from the Prefect CLI as

```bash
$ prefect agent local start
```

!!! tip API Keys <Badge text="Cloud"/>
    When using Prefect Cloud, this will require a service account API key, see
    [here](./overview.md#api_keys) for more information.
:::

Below we cover a few common configuration options, see the [CLI
docs](/api/latest/cli/agent.md#local-start) for a full list of options.

### Labels

Like [all agents](./overview.md#labels), the local agent can optionally be
configured with labels. These are used to filter which flow runs an agent can
deploy.

```bash
$ prefect agent local start -l label1 -l label2
```

By default, the local agent will include a label for its hostname. This is
useful for flows using [Local
Storage](/orchestration/flow_config/storage.md#local), which also adds this
label by default. To disable this default label, use the `--no-hostname-label`
flag:

```bash
$ prefect agent local start --no-hostname-label
```

### Streaming Flow Run Logs

The local agent includes an option to stream logs from its running flows to the
console, rather than relying on Prefect Cloud/Server to access these logs. This
can be useful for debugging flow runs locally. To enable, use the
`--show-flow-logs` flag:

```bash
$ prefect agent local start --show-flow-logs
```

## Using with Supervisor

[Supervisor](http://supervisord.org) is a tool for managing long running
processes on a UNIX-like operating system. This can be useful for deployments
where you want to ensure you have a Prefect Local Agent always running in the
background.

The Prefect CLI provides a command for generating an example `supervisord.conf`
file for managing a local agent.

```bash
$ prefect agent local install
```

This outputs example contents of a `supervisord.conf`. The `install` command
accepts many of the same arguments as `prefect agent local start`, allowing for
easy configuration. See the [CLI docs](/api/latest/cli/agent.md#local-install)
for information on all available options. Likewise, see the
[Supervisor](http://supervisord.org) docs for more information on installing
and using supervisor.


## Multiple local agents with the same label

We recommend assigning a unique label to each agent, particularly when 
running multiple local agents. While Prefect Cloud has a mechanism to ensure 
that each flow run gets executed only once, race conditions may occur if you 
have multiple agents with the same label. The example below shows that instead 
of starting all agents with label "prod", we can add a number to make it unique.

```bash
$ prefect agent local start --no-hostname-label --label prod1
$ prefect agent local start --no-hostname-label --label prod2
```

Currently, Prefect has no notion of a task queue that would allow
load-balancing flow runs across multiple agents based on available 
resources on each agent. If you need such functionality, 
you would need to assign unique labels to your agents, 
and then assign corresponding labels to your flows 
to spread the load across multiple agents. For instance:

Flow 1:
```python
from prefect.run_configs import UniversalRun
...
with Flow(name="example1", run_config=UniversalRun(labels=["prod1"])) as flow:
```

Flow 2:
```python
from prefect.run_configs import UniversalRun
...
with Flow(name="example2", run_config=UniversalRun(labels=["prod2"])) as flow:
```

To help with scale, we recommend using one of the other agents, such as:
- [KubernetesAgent](/orchestration/agents/kubernetes.md)
- [ECSAgent](/orchestration/agents/ecs.md)
- [VertexAgent](/orchestration/agents/vertex.md)