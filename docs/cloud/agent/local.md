# Local Agent

The Local Agent is designed to work in all environments with access to a Docker daemon. Local agents are most commonly used on personal machines for testing flow run deployments, but the local agent is by no means only useful for testing. In fact, it creates flow runs that interact with Prefect Cloud in the same way that it would on any other platform. This allows the Local Agent to be a fully functioning method of executing flows in conjunction with Prefect Cloud.

[[toc]]

### Requirements

::: warning Docker Daemon
The Local Agent requires an accessible Docker daemon. So if you are using this on your local machine make sure that you have Docker running. If Docker is not running, or the agent cannot access a daemon, it will notify users on start.
:::

### Usage

```
$ prefect agent start

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-09-01 12:24:59,261 - agent - INFO - Starting LocalAgent
2019-09-01 12:24:59,261 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-09-01 12:24:59,482 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-09-01 12:24:59,482 - agent - INFO - Waiting for flow runs...
```

The Local Agent can be started either through the Prefect CLI or by importing the `LocalAgent` class from the core library.

::: tip Tokens
There are a few ways in which you can specify a `RUNNER` API token:

- command argument `prefect agent start -t MY_TOKEN`
- environment variable `export PREFECT__CLOUD__AGENT__AUTH_TOKEN=MY_TOKEN`
- token will be used from `prefect.config.cloud.auth_token` if not provided from one of the two previous methods

:::

### Process

On start, the Local Agent verifies that it can connect to a Docker daemon. The default daemon location is determined by your system. `npipe:////./pipe/docker_engine` for Windows and `unix://var/run/docker.sock` for Unix. A separate Docker daemon location can be provided either through `base_url` when instantiating a `LocalAgent` object or through `--base-url` on the CLI.

The Local Agent periodically polls for new flow runs to execute. When a flow run is retrieved from Prefect Cloud, the agent confirms that the flow was deployed with a Docker storage option and uses the connected Docker daemon to create a container and run the flow.

The agent will block on the process in between finding the flow run and submitting it for execution if it has to pull the flow's Docker image.

::: tip no-pull
The local agent has an optional `--no-pull` flag where it will not attempt to pull the flow's Docker storage from a registry if desired. This is useful for cases in which a user may be testing the process completely locally without pushing the flow's Docker storage to a registry. Alternatively, if a flow's Docker storage does not have a `registry_url` specified then the Local Agent will not attempt to pull the image.
:::
