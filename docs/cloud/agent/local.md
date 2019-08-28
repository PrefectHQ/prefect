# Local Agent

The Local Agent is an agent designed to work in all environments which have access to a Docker daemon. This is most commonly used on personal machines as a way of testing flow run deployments in conjunction with Cloud. It does not mean that this agent is only synonymous with testing! In fact, it creates flow runs that interact with Prefect Cloud in the same way that it would on any other platform. This allows the Local Agent to be a fully functioning method of executing flows in conjunction with Prefect Cloud.

### Requirements

::: warning Docker Daemon
In order for the Local Agent to operate it requires a Docker daemon to be accessible. So if you are using this on your local machine make sure that you have Docker running. If Docker is not running, or the agent cannot access a daemon, it will notify users on start.
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
There are a few ways in which you can specify an `AGENT` API token:

- command argument `prefect agent start -t MY_TOKEN`
- environment variable `export PREFECT__CLOUD__AGENT__API_TOKEN=MY_TOKEN`
- token will be used from `prefect.config.cloud.api_token` if not provided from one of the two previous methods

:::

### Process

The Local Agent periodically polls for new flow runs to execute. Once a flow run is found from Prefect Cloud it checks to make sure that the flow was deployed with a Docker storage option. If it was then it uses the Docker daemon that it connected to in order to create a container which runs the flow.

The agent will block on the process in between finding the flow run and submitting it for execution if it has to pull the flow's Docker image.

::: tip no-pull
The local agent has an optional `--no-pull` flag where it will not attempt to pull the flow's Docker storage from a registry if desired. This is useful for cases in which a user may be testing the process completely locally without pushing the flow's Docker storage to a registry.
:::
