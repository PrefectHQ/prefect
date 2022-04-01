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

Work queues and agents bridge the Prefect Orion server’s _orchestration environment_ with a user’s _execution environment_. Work queues define the work to be done and agents poll a specific work queue for new work.

More specifically:

- You create a work queue on the server. Work queues collect scheduled runs for deployments that match their filter criteria. 
- You run an agent in the execution environment. Agents poll a specific work queue for new work, take scheduled work from the server, and deploy it for execution.

To run orchestrated deployments, you must configure at least one work queue and agent.

To configure a work queue and agent for orchestrated deployments:

1. [Create a work queue](#work-queue-configuration)
2. [Start an agent](#agent-configuration)

!!! note "Agent role has changed from Prefect 1.0"
    Work queues are a new concept. The role of agents has changed from their implementation in Prefect 1.0. If you're familiar with that model, please take some time to understand the new work queue/agent model. It requires a little more setup, but offers much greater control and flexibility with how deployments are executed.

    Key changes: 
    
    - Work queues contain all the logic about what flows run and how. Agents just pick up work from queues and execute the flows.
    - There is no global agent that picks up orchestrated work by default. You must configure a work queue and agent.

## Work queue overview

Work queues organize work that [agents](#agent-overview) can pick up to execute. Work queue configuration determines what work will be picked up.

Work queues contain scheduled runs from any deployments that match the queue criteria. Criteria can include:

- Deployment IDs
- Tags
- Flow runners

These criteria can be modified at any time, and agent processes requesting work for a specific queue will only see matching runs.

### Work queue configuration

You can configure work queues by using:

- Prefect Orion API or UI (planned)
- Prefect CLI commands

To configure a work queue to handle specific work, you can specify:

- One or more tags, which can be tags on flows, flow runs, or deployments.
- One or more deployment IDs
- One or more flow runner types

Only scheduled work meeting the specified criteria will route through the worker queue to available agents.

To configure a work queue, use the `prefect work-queue create` CLI command:

```bash
prefect work-queue create [OPTIONS] NAME
```

`NAME` is a required, unique name for the work queue.

Optional configuration parameters you can specify to filter work on the queue include:

| Option | Description |
| --- | --- |
| -t, --tag          | One or more tags. |
| -d, --deployment   | One or more deployment IDs. |
| -fr, --flow-runner | One or more [flow runner types](/concepts/flow-runners/). |

For example, to create a work queue called `test_queue` for a specific deployment with ID `'156edead-fe6a-4783-a618-21d3a63e95c4'`, you would run this command: 

```bash
$ prefect work-queue create -d '156edead-fe6a-4783-a618-21d3a63e95c4' test_queue
UUID('acffbcc8-ae65-4c83-a38a-96e2e5e5b441')
```

On success, the command returns the ID of the newly created work queue, which can then be used to start agents that poll this queue for work or perform additional configuration of the queue

Tags and IDs can be found in the UI or through the CLI. For example, if you wanted to find the ID and tags on a specific deployment, you could do the following:

```bash
$ prefect deployment inspect danny-trejflow/danny_trejflow_deployment
Deployment(
    id='156edead-fe6a-4783-a618-21d3a63e95c4',
    created='5 hours ago',
    updated='21 seconds ago',
    name='danny_trejflow_deployment',
    flow_id='2881404b-f111-425c-bc5a-e400b3b3761e',
    flow_data=DataDocument(encoding='blockstorage'),
    tags=['test'],
    flow_runner=FlowRunnerSettings()
)
```

### Viewing work queues

At any time, users can see a UI dashboard filtered to show a work queue.

To view work queues with the Prefect CLI, you can:

- List (`ls`) all available queues
- Inspect (`inspect`) the details of a queue by ID
- Preview (`preview`) scheduled work for a queue by ID

`prefect work-queue ls` lists all configured work queues for the server.

```bash
$ prefect work-queue ls
                                         Work Queues
┏━━━━━━━━━━━━━━━━━━━━┳┳┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                 ID ┃┃┃ Filter                                                             ┃
┡━━━━━━━━━━━━━━━━━━━━╇╇╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ acffbcc8-ae65-4c8… │││ {"tags": null, "deployment_ids": ["156edead-fe6a-4783-a618-21d3a6… │
└────────────────────┴┴┴────────────────────────────────────────────────────────────────────┘
                                 (**) denotes a paused queue
```

`prefect work-queue inspect` provides all configuration metadata for a specific work queue by ID.

```bash
$ prefect work-queue inspect 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
WorkQueue(
    id='acffbcc8-ae65-4c83-a38a-96e2e5e5b441',
    created='1 hour ago',
    updated='1 hour ago',
    filter=QueueFilter(deployment_ids="[UUID('156edead-fe6a-4783-a618-21d3a63e95c4')]"),
    name='danny_queue'
)
```

`prefect work-queue preview` displays scheduled flow runs for a specific work queue by ID for the upcoming hour. The optional `--hours` flag lets you specify the number of hours to look ahead. 

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

### Pausing and deleting work queues

A work queue can be paused at any time to stop the delivery of work to agents. Paused agents will not receive any work when polling.

To pause a work queue through the Prefect CLI, use the `prefect work-queue pause` command with the work queue ID:

```bash
$ prefect work-queue pause 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
Paused work queue acffbcc8-ae65-4c83-a38a-96e2e5e5b441
```

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

When work queues are configured, you can start an agent that corresponds to a specific work queue. 

You must start an agent within the environment in which it will execute flow runs. 

1. Install Prefect in the environment.
2. Using the [work queue ID](#work-queue-configuration) for the work queue the agent should poll for work, run the following CLI command to start an agent:

```bash
$ prefect agent start [OPTIONS] WORK_QUEUE_ID
```

For example:

```bash
$ prefect agent start 'acffbcc8-ae65-4c83-a38a-96e2e5e5b441'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started!
```

By default, the agent polls its work queue API specified by the `PREFECT_API_URL` environment variable. To configure the agent to poll from a different server location, use the `--api` flag, specifying the URL of the server.

