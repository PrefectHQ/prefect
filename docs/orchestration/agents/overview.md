# Overview

Prefect Agents are lightweight processes for orchestrating flow runs. Agents
run inside a user's architecture, and are responsible for starting and
monitoring flow runs. During operation the agent process queries the Prefect
API for any scheduled flow runs, and allocates resources for them on their
respective deployment platforms.

Note that both Prefect Agents (and flow runs) only send requests _out_ to the
Prefect API, and never receive requests themselves. This is part of our [Hybrid
Execution
Model](https://medium.com/the-prefect-blog/the-prefect-hybrid-model-1b70c7fd296),
and helps keep your code and data safe.

A single agent can manage many concurrent flow runs - the only reason to have
multiple active agents is if you need to support flow runs on different
deployment platforms.

## Agent Types

Prefect supports several different agent types for deploying on different
platforms.

- **Local**: The [Local Agent](./local.md) executes flow runs as local processes.

- **Docker**: The [Docker Agent](./docker.md) executes flow runs in docker
  containers.

- **Kubernetes**: The [Kubernetes Agent](./kubernetes.md) executes flow runs as
  [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/).

- **AWS ECS**: The [ECS Agent](./ecs.md) executes flow runs as [AWS ECS
  tasks](https://aws.amazon.com/ecs/) (on either ECS or Fargate).

See their respective documentation for more information on each type.

## Usage

Prefect agents can be started via the CLI, using `prefect agent <AGENT TYPE> start`. For example, to start a local agent:

```
prefect agent local start
```

Alternatively, all Prefect Agents can also be run using the Python API.

```python
from prefect.agent.local import LocalAgent

LocalAgent().start()
```

## Common Configuration Options

The following configuration options are shared for all agents.

### Authentication <Badge text="Cloud"/>

Prefect agents rely on the use of an API key from Prefect Cloud. For information on how to create and configure API keys, see the
[API key documentation](../concepts/api_keys.md).

In addition to the methods outlined there, you may pass an API key via CLI to an agent

```bash
$ prefect agent <agent-type> start --key "API_KEY"
```

### Prefect API Address

Prefect agents query the API for any pending flow runs. By default the address
used is:

- `https://api.prefect.io` for Prefect Cloud
- `http://localhost:4200` for Prefect Server

If needed, you can manually configure the address through the CLI:

```bash
prefect agent <AGENT TYPE> start --api <API ADDRESS>
```

### Labels

Agents have an optional `labels` argument which allows for separation of
execution when using multiple agents. This is especially useful for teams
wanting to run specific flows on different clusters. For more information on
labels and how to use them see the
[Run Configuration docs](../flow_config/run_configs.md#labels).

By default, agents have no set labels and will only pick up runs from flows
with no specified labels. Labels can be provided to an agent
through a few methods:

:::: tabs
::: tab CLI

```bash
prefect agent <AGENT TYPE> start --label dev --label staging
```

:::

::: tab Python API

```python
from prefect.agent.docker import DockerAgent

DockerAgent(labels=["dev", "staging"]).start()
```

:::

::: tab Prefect Config

```toml
# ~/.prefect/config.toml
[cloud.agent]
labels = ["dev", "staging"]
```

:::

::: tab Environment Variable

```bash
export PREFECT__CLOUD__AGENT__LABELS='["dev", "staging"]'
```

:::
::::

### Environment Variables

All agents have a `--env` flag for configuring environment variables to set on
all flow runs managed by that agent. This can be useful for things you want
applied to _all_ flow runs, whereas the `env` option in a flow's
[RunConfig](/orchestration/flow_config/run_configs.md) only applies to runs of a
specific flow.

:::: tabs
::: tab CLI

```bash
prefect agent <AGENT TYPE> start --env KEY=VALUE --env KEY2=VALUE2
```

:::

::: tab Python API

```python
from prefect.agent.docker import DockerAgent

DockerAgent(env_vars={"KEY": "VALUE", "KEY2": "VALUE2"})
```

:::
::::

### Agent Automations <Badge text="Cloud"/>

Users on Standard or Enterprise licenses in Cloud can create an agent [automation](orchestration/concepts/automations.html) to notify them if all agents from a configuration group (agent config ids can be added to multiple agents) have not queried for work in a certain time frame.   To do so go to the [automations tab of the dashboard](https://cloud.prefect.io/automations=) in the UI and set up an agent configuration then copy the agent config id that is provided once your automation is created.  You can then provide the agent configuration to your agent using the --agent-config-id flag:

```bash
prefect agent <AGENT TYPE> start --agent-config-id <AGENT CONFIG ID>
```

Note - Agent automations can only be added as a flag when starting an agent at present.  They can not be added at install. 

### Health Checks

Agents can optionally run a private HTTP server for use as a health check.
Health checks can be used by common orchestration services (e.g.
`supervisord`, `docker`, `kubernetes`, ...) to check that the agent is
running properly and take actions (such as restarting the agent) if it's not.

A few ways to configure:

:::: tabs
::: tab CLI

```bash
prefect agent <AGENT TYPE> start --agent-address http://localhost:8080
```

:::

::: tab Python API

```python
from prefect.agent.docker import DockerAgent

DockerAgent(agent_address="http://localhost:8080").start()
```

:::

::: tab Prefect Config

```toml
# ~/.prefect/config.toml
[cloud.agent]
agent_address = "http://localhost:8080"
```

:::

::: tab Environment Variable

```bash
$ export PREFECT__CLOUD__AGENT__AGENT_ADDRESS=http://localhost:8080
```

:::
::::

If enabled, the HTTP health check will be available via the `/api/health`
route at the configured agent address. This route returns `200 OK` if the
agent is healthy, and will error otherwise.
