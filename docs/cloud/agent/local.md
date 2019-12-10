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

# Register Flow to Prefect Cloud
flow.register("My Project")

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

# Register Flow to Prefect Cloud
flow.register("My Project")
```

This Flow is registered with Prefect Cloud with the actual Flow code stored in your local `~/.prefect/flows` directory. Now we can start a Local Agent from the CLI and tell it to look for scheduled runs for the _Welcome Flow_.

```
$ prefect agent start -t TOKEN -l welcome-flow

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-11-11 13:26:41,443 - agent - INFO - Starting LocalAgent with labels ['hostname.local', 's3-flow-storage', 'gcs-flow-storage']
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

### Installation

The Prefect CLI provides commands for installing agents on their respective platforms.

```
$ prefect agent install --help
Usage: prefect agent install [OPTIONS] NAME

  Install an agent. Outputs configuration text which can be used to install
  on various platforms. The Prefect image version will default to your local
  `prefect.__version__`

  Arguments:
      name                        TEXT    The name of an agent to install (e.g. `kubernetes`, `local`)

  Options:
      --token, -t                 TEXT    A Prefect Cloud API token
      --label, -l                 TEXT    Labels the agent will use to query for flow runs
                                          Multiple values supported e.g. `-l label1 -l label2`

  Kubernetes Agent Options:
      --api, -a                   TEXT    A Prefect Cloud API URL
      --namespace, -n             TEXT    Agent namespace to launch workloads
      --image-pull-secrets, -i    TEXT    Name of image pull secrets to use for workloads
      --resource-manager                  Enable resource manager on install

  Local Agent Options:
      --import-path, -p           TEXT    Absolute import paths to provide to the local agent.
                                          Multiple values supported e.g. `-p /root/my_scripts -p /utilities`
      --show-flow-logs, -f                Display logging output from flows run by the agent

Options:
  -h, --help  Show this message and exit.
```

The Local Agent installation outputs a file for [Supervisor](http://supervisord.org/installing.html) to manage the process. Since you're already using Prefect then Supervisor can be quickly and easily installed with `pip install supervisor`. For more information on Supervisor installation visit their [documentation](http://supervisord.org/installing.html).

The Prefect CLI has an installation command for the Local Agent which will output a `supervisord.conf` file that you can save and run using Supervisor. To see the contents of what this file will look like run the following command:

```bash
$ prefect agent install local --token $YOUR_RUNNER_TOKEN
```

This will give you output that you can provide to Supervisor in order to run your Local Agent. To run this for the first time save this output to a file called `supervisord.conf` and run the following command to start your Local Agent from the `supervisord.conf` file:

```
$ supervisord
```

Your Local Agent is now up and running in the background with Supervisor! This is an extermely useful tool for managing Agent processes in a non-invasive way and should work on any Unix based machine.

### Useful Supervisor Commands

To open an interactive prompt for inspection:

```
$ supervisorctl
```

If you ever need to edit your `supervisord.conf` file and restart:

```
$ supervisorctl reload
```

To inspect the status of your Local Agent use the interactive supervisorctl command:

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

When started, the Local Agent will use [Environment Labels](/cloud/execution/overview.html#environments) to watch for scheduled Flow runs that partain to a particular flow. This means that starting a Local Agent by calling `flow.run_agent()` will only pick up runs of that specific Flow.

The Local Agent periodically polls for new Flow runs to execute. When a Flow run is retrieved from Prefect Cloud, the Agent confirms that the Flow was registered with a Local storage option and runs that Flow in a subprocess.
