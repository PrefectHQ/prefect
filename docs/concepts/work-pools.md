---
description: Prefect work pools route deployment flow runs to agents. Prefect workers and agents poll work pools for new runs to execute.
tags:
    - work pools
    - workers
    - agents
    - orchestration
    - flow runs
    - deployments
    - schedules
    - concurrency limits
    - priority
search:
  boost: 2
---

# Work Pools, Workers & Agents

![flow-deployment-end-to-end](/img/concepts/flow-deployment-end-to-end.png)

Work pools, workers and agents, bridge the Prefect _orchestration environment_ with your _execution environment_. When a [deployment](/concepts/deployments/) creates a flow run, it is submitted to a specific work pool for scheduling. A worker or agent running in the execution environment can poll its respective work pool for new runs to execute, or the work pool can submit flow runs to serverless infrastructure directly, depending on your configuration.

Each work pool has a default queue that all runs will be sent to. Work queues are automatically created whenever they are referenced by either a deployment or an agent. For most applications, this automatic behavior will be sufficient to run flows as expected. For advanced needs, additional queues can be created to enable a greater degree of control over work delivery. See [work pool configuration](#work-pool-configuration) for more information.

To run deployments, you must configure at least one agent or worker (and its associated work pool):

1. [Start an agent](#starting-an-agent)
2. [Configure a work pool](#work-pool-configuration) (optional)

## Agent overview

Agent processes are lightweight polling services that get scheduled work from a [work pool](#work-pool-overview) and deploy the corresponding flow runs. 

Agents poll for work every 15 seconds by default. This interval is configurable in your [profile settings](/concepts/settings/) with the `PREFECT_AGENT_QUERY_INTERVAL` setting.

It is possible for multiple agent processes to be started for a single work pool. Each agent process sends a unique ID to the server to help disambiguate themselves and let users know how many agents are active.

### Agent options

Agents are configured to pull work from one or more work pool queues. If the agent references a work queue that doesn't exist, it will be created automatically.

Configuration parameters you can specify when starting an agent include:

| Option                                            | Description                                                                                                                                                                                  |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--api`                                           | The API URL for the Prefect server. Default is the value of `PREFECT_API_URL`.                                                                                                               |
| `--hide-welcome`                                  | Do not display the startup ASCII art for the agent process.                                                                                                                                  |
| `--limit`                                         | Maximum number of flow runs to start simultaneously. [default: None]                                                                                                                         |
| `--match`, `-m`                                   | Dynamically matches work queue names with the specified prefix for the agent to pull from,for example `dev-` will match all work queues with a name that starts with `dev-`. [default: None] |
| `--pool`, `-p`                                    | A work pool name for the agent to pull from. [default: None]                                                                                                                                 |
| <span class="no-wrap">`--prefetch-seconds`</span> | The amount of time before a flow run's scheduled start time to begin submission. Default is the value of `PREFECT_AGENT_PREFETCH_SECONDS`.                                                   |
| `--run-once`                                      | Only run agent polling once. By default, the agent runs forever. [default: no-run-once]                                                                                                      |
| `--work-queue`, `-q`                              | One or more work queue names for the agent to pull from. [default: None]                                                                                                                     |

You must start an agent within an environment that can access or create the infrastructure needed to execute flow runs. Your agent will deploy flow runs to the infrastructure specified by the deployment.

!!! tip "Prefect must be installed in execution environments"
    Prefect must be installed in any environment in which you intend to run the agent or execute a flow run.

!!! tip "`PREFECT_API_URL` and `PREFECT_API_KEY` settings for agents"
    `PREFECT_API_URL` must be set for the environment in which your agent is running or specified when starting the agent with the `--api` flag. You must also have a user or service account with the `Worker` role, which can be configured by setting the `PREFECT_API_KEY`.

    If you want an agent to communicate with Prefect Cloud or a Prefect server from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.

### Starting an agent

Use the `prefect agent start` CLI command to start an agent. You must pass at least one work pool name or match string that the agent will poll for work. If the work pool does not exist, it will be created.

<div class="terminal">
```bash
$ prefect agent start -p [work pool name]
```
</div>

For example:

<div class="terminal">
```bash
$ prefect agent start -p "my-pool"
Starting agent with ephemeral API...
  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|

Agent started! Looking for work from work pool 'my-pool'...
```
</div>

In this case, Prefect automatically created a new `my-queue` work queue.

By default, the agent polls the API specified by the `PREFECT_API_URL` environment variable. To configure the agent to poll from a different server location, use the `--api` flag, specifying the URL of the server.

In addition, agents can match multiple queues in a work pool by providing a `--match` string instead of specifying all of the queues. The agent will poll every queue with a name that starts with the given string. New queues matching this prefix will be found by the agent without needing to restart it.

For example:

<div class="terminal">
```bash
$ prefect agent start --match "foo-"
```
</div>

This example will poll every work queue that starts with "foo-".

### Configuring prefetch

By default, the agent begins submission of flow runs a short time (10 seconds) before they are scheduled to run. This allows time for the infrastructure to be created, so the flow run can start on time. In some cases, infrastructure will take longer than this to actually start the flow run. In these cases, the prefetch can be increased using the `--prefetch-seconds` option or the `PREFECT_AGENT_PREFETCH_SECONDS` setting. Submission can begin an arbitrary amount of time before the flow run is scheduled to start. If this value is _larger_ than the amount of time it takes for the infrastructure to start, the flow run will _wait_ until its scheduled start time. This allows flow runs to start exactly on time.

## Work pool overview

Work pools organize work for execution. Work pools have types corresponding to the infrastructure will execute the flow code, as well as the delivery method of work to that environment. Pull work pools require [agents](#agent-overview) or [workers](#worker-overview) to poll the work pool for flow runs to execute. Push work pools can submit runs directly to serverless infrastructure providers like Cloud Run, Azure Container Instances, and AWS ECS without the need for an agent or worker.

!!! tip "Work pools are like pub/sub topics"
    It's helpful to think of work pools as a way to coordinate (potentially many) deployments with (potentially many) agents through a known channel: the pool itself. This is similar to how "topics" are used to connect producers and consumers in a pub/sub or message-based system. By switching a deployment's work pool, users can quickly change the agent that will execute their runs, making it easy to promote runs through environments or even debug locally.

In addition, users can control aspects of work pool behavior, like how many runs the pool allows to be run concurrently or pausing delivery entirely. These options can be modified at any time, and any agent processes requesting work for a specific pool will only see matching flow runs.

### Work pool configuration

You can configure work pools by using:

 
- Prefect CLI commands
- Prefect Python API
- Prefect UI

To manage work pools in the UI, click the **Work Pools** icon. This displays a list of currently configured work pools.

![The UI displays a list of configured work pools](/img/ui/work-pool-list.png)

You can pause a work pool from this page by using the toggle.

Select the **+** button to create a new work pool. You'll be able to specify the details for work served by this work pool.

To configure a work pool via the Prefect CLI, use the `prefect work-pool create` command:

<div class="terminal">
```bash
prefect work-pool create [OPTIONS] NAME
```
</div>

`NAME` is a required, unique name for the work pool.

Optional configuration parameters you can specify to filter work on the pool include:

| Option     | Description                                                                                    |
| ---------- | ---------------------------------------------------------------------------------------------- |
| `--paused` | If provided, the work pool will be created in a paused state.                                  |
| `--type`   | The type of infrastructure that can execute runs from this work pool. [default: prefect-agent] |

For example, to create a work pool called `test-pool`, you would run this command: 

<div class="terminal">

```bash
$ prefect work-pool create test-pool

Created work pool with properties:
    name - 'test-pool'
    id - a51adf8c-58bb-4949-abe6-1b87af46eabd
    concurrency limit - None

Start an agent to pick up flows from the work pool:
    prefect agent start -p 'test-pool'

Inspect the work pool:
    prefect work-pool inspect 'test-pool'
```
</div>

On success, the command returns the details of the newly created work pool.

#### Base Job Template

Each work pool has a base job template that allows the customization of the behavior of the worker executing flow runs from the work pool. 

The base job template acts as a contract defining the configuration passed to the worker for each flow run and the options available to deployment creators to customize worker behavior per deployment. 

A base job template comprises a `job_configuration` section and a `variables` section. 

The `variables` section defines the fields available to be customized per deployment. The `variables` section follows the [OpenAPI specification](https://swagger.io/specification/), which allows work pool creators to place limits on provided values (type, minimum, maximum, etc.). 

The job configuration section defines how values provided for fields in the variables section should be translated into the configuration given to a worker when executing a flow run. 

The values in the `job_configuration` can use placeholders to reference values provided in the `variables` section. Placeholders are declared using double curly braces, e.g., `{{ variable_name }}`. `job_configuration` values can also be hard-coded if the value should not be customizable.

Each worker type is configured with a default base job template, making it easy to start with a work pool. The default base template defines fields that can be edited on a per-deployment basis or for the entire work pool via the Prefect API and UI.

For example, if we create a `process` work pool named 'above-ground' via the CLI:

```bash
$ prefect work-pool create --type process above-ground
```

We see these configuration options available in the Prefect UI:
![process work pool configuration options](/img/ui/process-work-pool-config.png)


For a `process` work pool with the default base job template, we can set environment variables for spawned processes, set the working directory to execute flows, and control whether the flow run output is streamed to workers' standard output. You can also see an example of JSON formatted base job template with the 'Advanced' tab.

You can override each of these attributes on a per-deployment basis. When deploying a flow, you can specify these overrides in the `work_pool.job_variables` section of a `deployment.yaml`.

If we wanted to turn off streaming output for a specific deployment, we could add the following to our `deployment.yaml`:

```yaml
work_pool:
    name: above-ground  
    job_variables:
        stream_output: false
```

!!! tip "Advanced Customization of the Base Job Template"
    For advanced use cases, users can create work pools with fully customizable job templates. This customization is available when creating or editing a work pool on the 'Advanced' tab within the UI.
    
    Advanced customization is useful anytime the underlying infrastructure supports a high degree of customization. In these scenarios a work pool job template allows you to expose a minimal and easy-to-digest set of options to deployment authors.  Additionally, these options are the _only_ customizable aspects for deployment infrastructure, which can be useful for restricting functionality in secure environments. For example, the `kubernetes` worker type allows users to specify a custom job template that can be used to configure the manifest that workers use to create jobs for flow execution. 
    
    For more information and advanced configuration examples, see the [Kubernetes Worker](https://prefecthq.github.io/prefect-kubernetes/worker/) documentation.

### Viewing work pools

At any time, users can see and edit configured work pools in the Prefect UI.

![The UI displays a list of configured work pools](/img/ui/work-pool-list.png)

To view work pools with the Prefect CLI, you can:

- List (`ls`) all available pools
- Inspect (`inspect`) the details of a single pool
- Preview (`preview`) scheduled work for a single pool

`prefect work-pool ls` lists all configured work pools for the server.

<div class="terminal">
```bash
$ prefect work-pool ls
prefect work-pool ls
                               Work pools
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Name       ┃    Type        ┃                                   ID ┃ Concurrency Limit ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ barbeque   │ prefect-agent  │ 72c0a101-b3e2-4448-b5f8-a8c5184abd17 │ None              │
│ k8s-pool   │  prefect-agent │ 7b6e3523-d35b-4882-84a7-7a107325bb3f │ None              │
│ test-pool  │  prefect-agent │ a51adf8c-58bb-4949-abe6-1b87af46eabd │ None              │
└────────────┴────────────────┴──────────────────────────────────────┴───────────────────┘
                       (**) denotes a paused pool
```
</div>

`prefect work-pool inspect` provides all configuration metadata for a specific work pool by ID.

<div class="terminal">
```bash
$ prefect work-pool inspect 'test-pool'
Workpool(
    id='a51adf8c-58bb-4949-abe6-1b87af46eabd',
    created='2 minutes ago',
    updated='2 minutes ago',
    name='test-pool',
    filter=None,
)
```
</div>

`prefect work-pool preview` displays scheduled flow runs for a specific work pool by ID for the upcoming hour. The optional `--hours` flag lets you specify the number of hours to look ahead. 

<div class="terminal">
```bash
$ prefect work-pool preview 'test-pool' --hours 12 
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Scheduled Star… ┃ Run ID                     ┃ Name         ┃ Deployment ID               ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2022-02-26 06:… │ 741483d4-dc90-4913-b88d-0… │ messy-petrel │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 05:… │ 14e23a19-a51b-4833-9322-5… │ unselfish-g… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 04:… │ deb44d4d-5fa2-4f70-a370-e… │ solid-ostri… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 03:… │ 07374b5c-121f-4c8d-9105-b… │ sophisticat… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 02:… │ 545bc975-b694-4ece-9def-8… │ gorgeous-mo… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 01:… │ 704f2d67-9dfa-4fb8-9784-4… │ sassy-hedge… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-26 00:… │ 691312f0-d142-4218-b617-a… │ sincere-moo… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-25 23:… │ 7cb3ff96-606b-4d8c-8a33-4… │ curious-cat… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-25 22:… │ 3ea559fe-cb34-43b0-8090-1… │ primitive-f… │ 156edead-fe6a-4783-a618-21… │
│ 2022-02-25 21:… │ 96212e80-426d-4bf4-9c49-e… │ phenomenal-… │ 156edead-fe6a-4783-a618-21… │
└─────────────────┴────────────────────────────┴──────────────┴─────────────────────────────┘
                                   (**) denotes a late run
```
</div>

### Pausing and deleting work pools

A work pool can be paused at any time to stop the delivery of work to agents. Agents will not receive any work when polling a paused pool.

To pause a work pool through the Prefect CLI, use the `prefect work-pool pause` command:

<div class="terminal">
```bash
$ prefect work-pool pause 'test-pool'
Paused work pool 'test-pool'
```
</div>

To resume a work pool through the Prefect CLI, use the `prefect work-pool resume` command with the work pool name.

To delete a work pool through the Prefect CLI, use the `prefect work-pool delete` command with the work pool name.

### Work pool concurrency

Each work pool can optionally restrict concurrent runs of matching flows. 

For example, a work pool with a concurrency limit of 5 will only release new work if fewer than 5 matching runs are currently in a `Running` or `Pending` state. If 3 runs are `Running` or `Pending`, polling the pool for work will only result in 2 new runs, even if there are many more available, to ensure that the concurrency limit is not exceeded.

When using the `prefect work-pool` Prefect CLI command to configure a work pool, the following subcommands set concurrency limits:

- `set-concurrency-limit`  sets a concurrency limit on a work pool.
- `clear-concurrency-limit` clears any concurrency limits from a work pool.

### Work queues

!!! tip "Advanced topic"
    Work queues do not require manual creation or configuration, because Prefect will automatically create them whenever needed. Managing work queues offers advanced control over how runs are executed.

Each work pool has a "default" queue that all work will be sent to by default. Additional queues can be added to a work pool. Work queues enable greater control over work delivery through fine grained priority and concurrency. Each work queue has a priority indicated by a unique positive integer. Lower numbers take greater priority in the allocation of work. Accordingly, new queues can be added without changing the rank of the higher-priority queues (e.g. no matter how many queues you add, the queue with priority `1` will always be the highest priority).

Work queues can also have their own concurrency limits. Note that each queue is also subject to the global work pool concurrency limit, which cannot be exceeded.

Together work queue priority and concurrency enable precise control over work. For example, a pool may have three queues: A "low" queue with priority `10` and no concurrency limit, a "high" queue with priority `5` and a concurrency limit of `3`, and a "critical" queue with priority `1` and a concurrency limit of `1`. This arrangement would enable a pattern in which there are two levels of priority, "high" and "low" for regularly scheduled flow runs, with the remaining "critical" queue for unplanned, urgent work, such as a backfill.

Priority is evaluated to determine the order in which flow runs are submitted for execution. 
If all flow runs are capable of being executed with no limitation due to concurrency or otherwise, priority is still used to determine order of submission, but there is no impact to execution.
If not all flow runs can be executed, usually as a result of concurrency limits, priority is used to determine which queues receive precedence to submit runs for execution.

Priority for flow run submission proceeds from the highest priority to the lowest priority. In the preceding example, all work from the "critical" queue (priority 1) will be submitted, before any work is submitted from "high" (priority 5). Once all work has been submitted from priority queue "critical", work from the "high" queue will begin submission. 

If new flow runs are received on the "critical" queue while flow runs are still in scheduled on the "high" and "low" queues, flow run submission goes back to ensuring all scheduled work is first satisfied from the highest priority queue, until it is empty, in waterfall fashion.

### Local debugging
As long as your deployment's infrastructure block supports it, you can use work pools to temporarily send runs to an agent running on your local machine for debugging by running `prefect agent start -p my-local-machine` and updating the deployment's work pool to `my-local-machine`.

## Worker Overview <span class="badge beta"></span>
!!! warning "Workers are a beta feature"
    Workers are a beta feature and are subject to change in future releases.

Workers are lightweight polling services that retrieve scheduled runs from a work pool and execute them.

Workers are similar to agents, but offer greater control over infrastructure configuration and the ability to route work to specific types of execution environments.

Workers each have a type corresponding to the execution environment to which they will submit flow runs. Workers are only able to join work pools that match their type. As a result, when deployments are assigned to a work pool, you know in which execution environment scheduled flow runs for that deployment will run.

### Worker Types

Below is a list of available worker types. Note that most worker types will require installation of an additional package.

| Worker Type | Description | Required Package |
| --- | --- | --- |
| [`process`](/api-ref/prefect/workers/process/) | Executes flow runs in subprocesses | |
| [`kubernetes`](https://prefecthq.github.io/prefect-kubernetes/worker/) | Executes flow runs as Kubernetes jobs | `prefect-kubernetes` |
| [`docker`](https://prefecthq.github.io/prefect-docker/worker/) | Executes flow runs within Docker containers | `prefect-docker` |
| [`ecs`](https://prefecthq.github.io/prefect-aws/ecs_worker/) | Executes flow runs as ECS tasks | `prefect-aws` |
| [`cloud-run`](https://prefecthq.github.io/prefect-gcp/worker/) | Executes flow runs as Google Cloud Run jobs | `prefect-gcp` |
| [`azure-container-instance`](https://prefecthq.github.io/prefect-azure/container_instance_worker/) | Execute flow runs in ACI containers | `prefect-azure` |

If you don’t see a worker type that meets your needs, consider [developing a new worker type](/guides/deployment/developing-a-new-worker-type/)!

### Worker Options
Workers poll for work from one or more queues within a work pool. If the worker references a work queue that doesn't exist, it will be created automatically. The worker CLI is able to infer the worker type from the work pool. Alternatively, you can also specify the worker type explicitly. If you supply the worker type to the worker CLI, a work pool will be created automatically if it doesn't exist (using default job settings).

Configuration parameters you can specify when starting a worker include:

| Option                                            | Description                                                                                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `--name`, `-n`                                    | The name to give to the started worker. If not provided, a unique name will be generated.                                                   |
| `--pool`, `-p`                                    | The work pool the started worker should poll.                                                                                               |
| `--work-queue`, `-q`                              | One or more work queue names for the worker to pull from. If not provided, the worker will pull from all work queues in the work pool.      |
| `--type`, `-t`                                    | The type of worker to start. If not provided, the worker type will be inferred from the work pool.                                          |
| <span class="no-wrap">`--prefetch-seconds`</span> | The amount of time before a flow run's scheduled start time to begin submission. Default is the value of `PREFECT_WORKER_PREFETCH_SECONDS`. |
| `--run-once`                                      | Only run worker polling once. By default, the worker runs forever.                                                                          |
| `--limit`, `-l`                                   | The maximum number of flow runs to start simultaneously.                                                                                    |
| `--with-healthcheck`                                   | Start a healthcheck server for the worker.                                                                                    |
| `--install-policy`                                   | Install policy to use workers from Prefect integration packages.                                                                                    |

You must start a worker within an environment that can access or create the infrastructure needed to execute flow runs. The worker will deploy flow runs to the infrastructure corresponding to the worker type. For example, if you start a worker with type `kubernetes`, the worker will deploy flow runs to a Kubernetes cluster.

!!! tip "Prefect must be installed in execution environments"
    Prefect must be installed in any environment (virtual environment, Docker container, etc.) where you intend to run the worker or execute a flow run.

!!! tip "`PREFECT_API_URL` and `PREFECT_API_KEY`settings for workers"
    `PREFECT_API_URL` must be set for the environment in which your worker is running. You must also have a user or service account with the `Worker` role, which can be configured by setting the `PREFECT_API_KEY`.

### Starting a Worker
Use the `prefect worker start` CLI command to start a worker. You must pass at least the work pool name. If the work pool does not exist, it will be created if the `--type` flag is used.
<div class="terminal">
```bash
$ prefect worker start -p [work pool name]
```
</div>
For example:
<div class="terminal">
```bash
prefect worker start -p "my-pool"
Discovered worker type 'process' for work pool 'my-pool'.
Worker 'ProcessWorker 65716280-96f8-420b-9300-7e94417f2673' started!
```
</div>
In this case, Prefect automatically discovered the worker type from the work pool.
To create a work pool and start a worker in one command, use the `--type` flag:
<div class="terminal">
```bash
prefect worker start -p "my-pool" --type "process"
Worker 'ProcessWorker d24f3768-62a9-4141-9480-a056b9539a25' started!
06:57:53.289 | INFO    | prefect.worker.process.processworker d24f3768-62a9-4141-9480-a056b9539a25 - Worker pool 'my-pool' created.
```
</div>
In addition, workers can limit the number of flow runs they will start simultaneously with the `--limit` flag. 
For example, to limit a worker to five concurrent flow runs:
<div class="terminal">
```bash
prefect worker start --pool "my-pool" --limit 5
```
</div>

### Configuring Prefetch
By default, the worker begins submitting flow runs a short time (10 seconds) before they are scheduled to run. This behavior allows time for the infrastructure to be created so that the flow run can start on time. 

In some cases, infrastructure will take longer than 10 seconds to start the flow run. The prefetch can be increased using the `--prefetch-seconds` option or the `PREFECT_WORKER_PREFETCH_SECONDS` setting.

If this value is _more_ than the amount of time it takes for the infrastructure to start, the flow run will _wait_ until its scheduled start time.

### Polling for work
Workers poll for work every 15 seconds by default. This interval is configurable in your [profile settings](/concepts/settings/) with the
`PREFECT_WORKER_QUERY_SECONDS` setting.

### Install Policy

The Prefect CLI can install the required package for Prefect-maintained worker types automatically. You can configure this behavior with the `--install-policy` option. The following are valid install policies

| Install Policy | Description |
| --- | --- |
| `always` | Always install the required package. Will update the required package to the most recent version if already installed. |
| <span class="no-wrap">`if-not-present`<span> | Install the required package if it is not already installed. |
| `never` | Never install the required package. |
| `prompt` | Prompt the user to choose whether to install the required package. This is the default install policy. If `prefect worker start` is run non-interactively, the `prompt` install policy will behave the same as `never`. |

### Additional Resources
- [How to run a Prefect 2 worker as a systemd service on Linux](https://discourse.prefect.io/t/how-to-run-a-prefect-2-worker-as-a-systemd-service-on-linux/1450)
