# Local Agent

The Local Agent is designed to operate in any environment that has Prefect installed. Common use cases for the Local Agent include testing Flows on personal machines, running in virtual boxes that don't use external tools such as Docker or Kubernetes, or quickly getting acclimated with using Prefect Cloud. The Local Agent is a fully functioning method of executing Flows in conjunction with Prefect Cloud however for production use our recommended use case involves using one of the other Agents which relies on Flows being stored in a containe registry registry for modularity and scale.

[[toc]]

### Requirements

The Local Agent has no outside dependencies and only requires that Prefect is installed!

### Usage

#### Start from Flow

The Local Agent can be started directly from a Flow object.

```python
import prefect
from prefect import task, Flow

@task
def welcome():
    logger = prefect.context["logger"]
    logger.info("Welcome")

flow = Flow("Welcome Flow", tasks=[welcome_logger])

# Deploy Flow to Prefect Cloud
flow.deploy("My Project")

# Spawn a local agent and run in process
flow.run_agent()

```

Since we do not provide a storage object to our Flow it defaults to using [`Local`](/api/unreleased/environments/storage.html#local) storage which automatically stores the flow in `~/.prefect/flows` and only agents running on this machine will be able to submit this Flow for execution. Once we call `run_agent` on the Flow a Local Agent will start and listen for scheduled work from Prefect Cloud.

#### Start from CLI

The Local Agent can also be started from the Prefect CLI in order to run Flows stored locally.

```python
import prefect
from prefect import task, Flow

@task
def welcome():
    logger = prefect.context["logger"]
    logger.info("Welcome")

flow = Flow("Welcome Flow", tasks=[welcome_logger])

# Deploy Flow to Prefect Cloud
flow.deploy("My Project")
```

This Flow is deployed to Prefect Cloud with the actual Flow code stored in your local `~/.prefect/flows` directory. Now we can start a Local Agent from the CLI and tell it to look for scheduled runs for the _Welcome Flow_.

```
$ prefect agent start -t TOKEN -l welcome-flow

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-11-11 13:26:41,443 - agent - INFO - Starting LocalAgent with labels ['welcome-flow', 'local']
2019-11-11 13:26:41,443 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-11-11 13:26:41,638 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-11-11 13:26:41,638 - agent - INFO - Waiting for flow runs...
```

The agent is started with the `-l/--label` _welcome-flow_. All Flows stored locally will exist with a slugified name and in this example _Welcome Flow_ becomes _welcome-flow_. This means that you can set your Local Agent to run multiple local Flows by providing a label for each Flow's slugified name.

::: tip Tokens
There are a few ways in which you can specify a `RUNNER` API token:

- command argument `prefect agent start -t MY_TOKEN`
- environment variable `export PREFECT__CLOUD__AGENT__AUTH_TOKEN=MY_TOKEN`
- token will be used from `prefect.config.cloud.auth_token` if not provided from one of the two previous methods
:::

### Process

When started, the Local Agent will use [Environment Labels](/cloud/execution/overview.html#environments) to watch for scheduled Flow runs that partain to a particular flow. This means that starting a Local Agent by calling `flow.run_agent()` will only pick up runs of that specific Flow.

The Local Agent periodically polls for new Flow runs to execute. When a Flow run is retrieved from Prefect Cloud, the Agent confirms that the Flow was deployed with a Local storage option and runs that Flow in a subprocess.
