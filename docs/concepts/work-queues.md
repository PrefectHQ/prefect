---
description: Prefect work queues define work to be done. Prefect agents poll a work queue for new work.
tags:
    - Orion
    - work queues
    - agents
    - orchestration
    - filters
    - flow runs
    - deployments
    - schedules
    - concurrency limits
---

# Work Queues and Agents

Work queues and agents bridge the Prefect Orion _orchestration environment_ with a user’s _execution environment_. Work queues define the work to be done and agents poll a specific work queue for new work.

More specifically:

- You create a work queue on the server. Work queues collect scheduled runs for deployments that match their filter criteria. 
- You run an agent in the execution environment. Agents poll a specific work queue for new flow runs, take scheduled flow runs from the server, and deploy them for execution.

To run orchestrated deployments, you must configure at least one work queue and agent.

To configure a work queue and agent for orchestrated deployments:

1. [Create a work queue](#work-queue-configuration)
2. [Start an agent](#agent-configuration)

!!! tip "Agent role has changed from Prefect 1.0"
    Work queues are a new concept. The role of agents has changed from their implementation in Prefect 1.0. If you're familiar with that model, please take some time to understand the new work queue/agent model. It requires a little more setup, but offers much greater control and flexibility with how deployments are executed.

    Key changes: 
    
    - Work queues contain all the logic about what flows run and how. Agents just pick up work from queues and execute the flows.
    - There is no global agent that picks up orchestrated work by default. You must configure a work queue and agent.

## Work queue overview

Work queues organize work that [agents](#agent-overview) can pick up to execute. Work queue configuration determines what work will be picked up.

Work queues contain scheduled runs from any deployments that match the queue criteria. Criteria is based on deployment _tags_ &mdash; all runs for deployments that have the tags defined on the queue will be picked up.

These criteria can be modified at any time, and agent processes requesting work for a specific queue will only see matching flow runs.

### Work queue configuration

You can configure work queues by using:

- Prefect UI [**Work Queues**](/ui/work-queues/) page
- Prefect CLI commands
- Prefect Python API

![Creating a new work queue in the Orion UI](/img/ui/work-queue-create.png)

To configure a work queue to handle specific work, you can specify filters by providing a list of tags. Only scheduled work that meets the specified criteria will route through the work queue to available agents.

!!! tip "Filters limit what work queues accept"
    Work queue filters are a powerful tool for routing flow runs to the agents most appropriate to execute them. To get the most out of work queues, it's important to understand that filters _limit_ the work queue to service only flow runs for deployments that meet _all_ of the filters you've set.
    
    If you set no filters at all on a work queue, the queue will service any flow run for any deployment. 
    
    If you set a filter for the tag `test`, it will service any flow for any deployment that has a `test` tag. 

    When setting filters on a work queue, we recommend setting the miniumum filters that achieve the flow run distribution you need. The flexibility of work queue filters means it's possible to create filters that accept no work at all. If you filter on tag `X` and tag `y`, but no runs have both tag `X` and `y`, then the queue won't route any flow runs.

To configure a work queue via the Prefect CLI, use the `prefect work-queue create` command:

<div class="terminal">
```bash
prefect work-queue create [OPTIONS] NAME
```
</div>

`NAME` is a required, unique name for the work queue.

Optional configuration parameters you can specify to filter work on the queue include:

| Option | Description |
| --- | --- |
| -l, --limit | The [concurrency limit](#work-queue-concurrency) to set on the queue. |
| -t, --tag   | One or more tags. |

For example, to create a work queue called `test_queue` for a specific tag `test`, you would run this command: 

<div class="terminal">
```bash
$ prefect work-queue create -t 'test' test_queue

Created work queue with properties:
    name - 'test_queue'
    uuid - 90e4f0fe-420b-4e4f-884c-ca0b105be2b8
    tags - ('test',)
    concurrency limit - None

Start an agent to pick up flows from the created work queue:
    prefect agent start '90e4f0fe-420b-4e4f-884c-ca0b105be2b8'

Inspect the created work queue:
    prefect work-queue inspect '90e4f0fe-420b-4e4f-884c-ca0b105be2b8'
```
</div>

On success, the command returns the details of the newly created work queue, which can then be used to start agents that poll this queue for work or perform additional configuration of the queue.

### Viewing work queues

At any time, users can see and edit configured work queues in the Prefect UI.

![The UI displays a list of configured work queues](/img/ui/work-queue-list.png)

To view work queues with the Prefect CLI, you can:

- List (`ls`) all available queues
- Inspect (`inspect`) the details of a queue by ID
- Preview (`preview`) scheduled work for a queue by ID

`prefect work-queue ls` lists all configured work queues for the server.

<div class="terminal">
```bash
$ prefect work-queue ls
                               Work Queues
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃                                   ID ┃ Name       ┃ Concurrency Limit ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 90e4f0fe-420b-4e4f-884c-ca0b105be2b8 │ test_queue │ None              │
│ 6202e5b1-8391-4856-a6dc-d480b92d4a6a │ k8s-queue  │ None              │
│ cda84217-f82b-4179-ad6c-bbafc1edc363 │ barbequeue │ None              │
└──────────────────────────────────────┴────────────┴───────────────────┘
                       (**) denotes a paused queue
```
</div>

`prefect work-queue inspect` provides all configuration metadata for a specific work queue by ID.

<div class="terminal">
```bash
$ prefect work-queue inspect '90e4f0fe-420b-4e4f-884c-ca0b105be2b8'
WorkQueue(
    id='90e4f0fe-420b-4e4f-884c-ca0b105be2b8',
    created='2 minutes ago',
    updated='2 minutes ago',
    filter=QueueFilter(tags=['test']),
    name='test_queue'
)
```
</div>

`prefect work-queue preview` displays scheduled flow runs for a specific work queue by ID for the upcoming hour. The optional `--hours` flag lets you specify the number of hours to look ahead. 

<div class="terminal">
```bash
$ prefect work-queue preview --hours 12 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
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

### Pausing and deleting work queues

A work queue can be paused at any time to stop the delivery of work to agents. Paused agents will not receive any work when polling.

To pause a work queue through the Prefect CLI, use the `prefect work-queue pause` command with the work queue ID:

<div class="terminal">
```bash
$ prefect work-queue pause 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
Paused work queue acffbcc8-ae65-4c83-a38a-96e2e5e5b441
```
</div>

To resume a work queue through the Prefect CLI, use the `prefect work-queue resume` command with the work queue ID.

To delete a work queue through the Prefect CLI, use the `prefect work-queue delete` command with the work queue ID.

### Work queue concurrency

Each work queue can optionally restrict concurrent runs of matching flows. 

For example, a work queue with a concurrency limit of 5 will only release new work if fewer than 5 matching runs are currently in a `Running` state. If 3 runs are `Running`, polling the queue for work will only result in 2 new runs, even if there are many more available, to ensure that the concurrency limit is not exceeded.

When using the `prefect work-queue` Prefect CLI command to configure a work queue, the following optional flags set concurrency limits:

- `set-concurrency-limit`  sets a concurrency limit on a work queue.
- `clear-concurrency-limit` clears any concurrency limits from a work queue.

## Agent overview

Agent processes are lightweight polling services that get scheduled work from a [work queue](#work-queue-overview) and deploy the corresponding flow runs. 

It is possible for multiple agent processes to be started for a single work queue, and each process sends a unique agent ID.

### Agent configuration

When work queues are configured, you can start an agent that corresponds to a specific work queue. Prefect also provides the ability to auto-create work queues on your behalf based on a set of tags passed to the `prefect agent start` command.

Configuration parameters you can specify when starting an agent include:

| Option | Description |
| --- | --- |
| --api TEXT     | The API URL for the Prefect Orion server. Default is the value of `PREFECT_API_URL`. |
| --hide-welcome | Do not display the startup ASCII art for the agent process. |
| -t, --tag      | One or more optional tags that will be used to create a work queue. |

You must start an agent within an environment that can access or create the infrastructure needed to execute flow runs. Your agent will deploy flow runs to the infrastructure specified by the deployment.

!!! tip "Prefect must be installed in execution environments"
    Prefect must be installed in any environment in which you intend to run the agent or execute a flow run.

!!! tip "`PREFECT_API_URL` setting for agents"
    `PREFECT_API_URL` must be set for the environment in which your agent is running. 

    If you want an agent to communicate with Prefect Cloud or a Prefect Orion API server from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.

Run the following `prefect agent start` CLI command to start an agent. You must pass the [work queue ID](#work-queue-configuration) for the queue the agent should poll for work.

<div class="terminal">
```bash
$ prefect agent start [OPTIONS] WORK_QUEUE_ID
```
</div>

For example:

<div class="terminal">
```bash
$ prefect agent start 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started!
```
</div>

Alternatively, start your agent with a set of tags and Prefect will create a work queue for you.

<div class="terminal">
```bash
$ prefect agent start -t demo
Created work queue 'Agent queue demo'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'Agent queue demo'...
```
</div>

In this case, Prefect automatically created a new `Agent queue demo` work queue that filters on a `demo` tag. Note that, if a work queue with equivalent settings already exists, Prefect uses that work queue rather than creating a new one.

By default, the agent polls its work queue API specified by the `PREFECT_API_URL` environment variable. To configure the agent to poll from a different server location, use the `--api` flag, specifying the URL of the server.

!!! tip "Agents can use work queue names"
    When starting an agent, you may reference the target work queue by name rather than ID. However, work queue names can be edited. Work queue IDs are idempotent.
