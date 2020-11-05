# Local Agent

The local agent is designed to operate in any environment in which Prefect is installed. Common use cases for the local agent include testing flows on personal machines, running in virtual boxes that don't use external tools such as Docker or Kubernetes, or quickly getting acclimated with the Prefect API. While the local agent is fully capable of executing flows in conjunction with the Prefect API, we generally recommend using one of the other agents to help with modularity and scale.

[[toc]]

### Requirements

The local agent has no outside dependencies and only requires that Prefect is installed!

If running the local agent inside a Docker container, we recommend you also use
an init process like [`tini`](https://github.com/krallin/tini). Running without
an init process may result in lingering zombie processes accumulating in your
container.

### Usage

#### Start from Flow

The local agent can be started directly from a Flow object.

```python
import prefect
from prefect import task, Flow

@task
def welcome_logger():
    logger = prefect.context["logger"]
    logger.info("Welcome")

flow = Flow("Welcome Flow", tasks=[welcome_logger])

# Register Flow with the Prefect API
flow.register(project_name="Hello, World!")

# Spawn a local agent and run in process
flow.run_agent()

```

Since we do not provide a storage object to our flow it defaults to using [`Local`](/api/latest/environments/storage.html#local) storage which automatically stores the flow in `~/.prefect/flows` and only agents running on this machine will be able to submit this flow for execution. Once we call `run_agent` on the flow a local agent will start and listen for scheduled work from Prefect Cloud.

#### Start from CLI

The local agent can also be started from the Prefect CLI in order to run flows stored locally.

```python
import prefect
from prefect import task, Flow

@task
def welcome():
    logger = prefect.context["logger"]
    logger.info("Welcome")

flow = Flow("Welcome Flow", tasks=[welcome_logger])

# Register Flow with the Prefect API
flow.register(project_name="Hello, World!")
```

This flow is registered with the Prefect API with the actual flow code stored in your local `~/.prefect/flows` directory. We can now start a local agent from the CLI and tell it to look for scheduled runs for the _Welcome Flow_.

```
$ prefect agent local start -t TOKEN -l welcome-flow

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-11-11 13:26:41,443 - agent - INFO - Starting LocalAgent with labels ['hostname.local', 'azure-flow-storage', 's3-flow-storage', 'gcs-flow-storage']
2019-11-11 13:26:41,443 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/orchestration/
2019-11-11 13:26:41,638 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-11-11 13:26:41,638 - agent - INFO - Waiting for flow runs...
```

The agent is started with the `-l/--label` _welcome-flow_. All flows stored locally will exist with a slugified name and in this example _Welcome Flow_ becomes _welcome-flow_. This means that you can set your local agent to run multiple local flows by providing a label for each flow's slugified name.

::: tip Tokens <Badge text="Cloud"/>
There are a few ways in which you can specify a `RUNNER` API token:

- command argument `prefect agent local start -t MY_TOKEN`
- environment variable `export PREFECT__CLOUD__AGENT__AUTH_TOKEN=MY_TOKEN`
- token will be used from `prefect.config.cloud.auth_token` if not provided from one of the two previous methods
  :::

### Installation

The Prefect CLI provides commands for installing agents on their respective platforms.

```
$ prefect agent local install --help
Usage: prefect agent local install [OPTIONS]

  Generate a supervisord.conf file for a Local agent

Options:
  -t, --token TEXT        A Prefect Cloud API token with RUNNER scope.
  -l, --label TEXT        Labels the agent will use to query for flow runs.
  -e, --env TEXT          Environment variables to set on each submitted flow
                          run.

  -p, --import-path TEXT  Import paths the local agent will add to all flow
                          runs.

  -f, --show-flow-logs    Display logging output from flows run by the agent.
  -h, --help              Show this message and exit.
```

The local agent installation outputs a file for [Supervisor](http://supervisord.org/installing.html) to manage the process. Since you're already using Prefect, Supervisor can be quickly and easily installed with `pip install supervisor`. For more information on Supervisor installation visit their [documentation](http://supervisord.org/installing.html).

The Prefect CLI has an installation command for the local agent which will output a `supervisord.conf` file that you can save and run using Supervisor. To see the contents of what this file will look like run the following command:

```bash
$ prefect agent local install --token $YOUR_RUNNER_TOKEN
```

This will give you output that you can provide to Supervisor in order to run your local agent. To run this for the first time save this output to a file called `supervisord.conf` and run the following command to start your local agent from the `supervisord.conf` file:

```
$ supervisord
```

Your local agent is now up and running in the background with Supervisor! This is an extermely useful tool for managing agent processes in a non-invasive way and should work on any Unix-based machine.

### Useful Supervisor Commands

To open an interactive prompt for inspection:

```
$ supervisorctl
```

If you ever need to edit your `supervisord.conf` file and restart:

```
$ supervisorctl reload
```

To inspect the status of your local agent use the interactive supervisorctl command:

```
$ supervisorctl
fg prefect-agent
```

To stop all running programs:

```
$ supervisorctl stop all
```

For more information on configuring supervisor, please see [http://supervisord.org/configuration.html](http://supervisord.org/configuration.html). To configure supervisor logging, please see [http://supervisord.org/logging.html](http://supervisord.org/logging.html).

### Process

When started, the local agent will use [environment labels](/orchestration/execution/overview.html#environments) to watch for scheduled Flow runs that partain to a particular flow. This means that starting a local agent by calling `flow.run_agent()` will only pick up runs of that specific flow.

The local agent periodically polls for new flow runs to execute. When a flow run is retrieved from the Prefect API, the agent confirms that the flow was registered with a local storage option and runs that flow in a subprocess.
