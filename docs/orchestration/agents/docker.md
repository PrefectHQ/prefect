# Docker Agent

The Docker agent executes flow runs in individual Docker containers. This
provides more isolation and control than the [Local Agent](./local.md), while
still working well on a single machine.

[[toc]]

## Requirements

The Docker agent requires a valid [Prefect
installation](/core/getting_started/installation.md), as well as an active and
accessible [Docker Daemon](https://docs.docker.com/get-docker/). Before
starting the Docker agent, you should check that you have Docker installed and
running. The minimum supported Docker engine version is v20.10.0.

## Flow Configuration

The Docker Agent will deploy flows using either a
[UniversalRun](/orchestration/flow_config/run_configs.md#universalrun) (the
default) or [DockerRun](/orchestration/flow_config/run_configs.md#dockerrun)
`run_config`. Using a `DockerRun` object lets you customize the deployment
environment for a flow (exposing `env`, `image`, etc...):

```python
from prefect.run_configs import DockerRun

# Configure extra environment variables for this flow,
# and set a custom image
flow.run_config = DockerRun(
    env={"SOME_VAR": "VALUE"},
    image="example/image-name:with-tag"
)
```

See the [DockerRun](/orchestration/flow_config/run_configs.md#dockerrun)
documentation for more information.

## Agent Configuration

The Docker agent can be started from the Prefect CLI as

```bash
prefect agent docker start
```

::: tip API Keys <Badge text="Cloud"/>
When using Prefect Cloud, this will require a service account API key, see
[here](./overview.md#api_keys) for more information.
:::

Below we cover a few common configuration options, see the [CLI
docs](/api/latest/cli/agent.md#docker-start) for a full list of options.

### Streaming Flow Run Logs

The Docker agent includes an option to stream logs from its running flows to the
console, rather than relying on Prefect Cloud/Server to access these logs. This
can be useful for debugging flow runs locally. To enable, use the
`--show-flow-logs` flag:

```bash
prefect agent docker start --show-flow-logs
```

### Configuring Networking

To add all flow run containers to an existing docker network, you can use the
`--network` flag.

```bash
prefect agent docker start --network my-network
```

### Mounting Volumes

To mount [volumes](https://docs.docker.com/storage/volumes/) in all flow run
containers, you can use the `--volume` flag. This matches the [`docker` CLI
`--volume` flag](https://docs.docker.com/storage/bind-mounts/) for using Docker
bind mounts. The flag can be provided multiple times to pass multiple volumes.

```bash
prefect agent docker start --volume /host/path:/container/path --volume /another/volume
```

### Disabling Image Pulling

The docker agent includes a `--no-pull` flag which disables its ability to pull
non-local images. This can be useful in debugging scenarios (where you don't
want to accidentally pull a remote image) or for extra security where you want
to ensure only local images are used.

```bash
prefect agent docker start --no-pull
```

### Docker Daemon Address

The Docker agent will use the default Docker daemon address for your system (
`npipe:////./pipe/docker_engine` on Windows, `unix://var/run/docker.sock` on
everything else). If you need to configure this manually, you can use the
`--base-url` option:

```bash
prefect agent docker start --base-url unix://some/other/docker.sock
```
