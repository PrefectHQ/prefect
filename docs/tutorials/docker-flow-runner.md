
# Docker integration

Prefect integrates with Docker via the [flow runner interface](/concepts/flow-runners/).
The [DockerFlowRunner](/api-ref/prefect/flow-runners.md#prefect.flow_runners.DockerFlowRunner) runs Prefect flows using [Docker containers](https://www.docker.com/resources/what-container).

## Requirements

- The [Docker Engine](https://docs.docker.com/engine/) must be installed and running on the same machine as your agent
- You must run a standalone Orion API (`prefect orion start`)

## Your first Docker deployment

Save the following script to the file `example-deployment.py`:

```python
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import DockerFlowRunner

@flow
def my_flow():
    print("Hello from Docker!")


DeploymentSpec(
    name="example",
    flow=my_flow,
    flow_runner=DockerFlowRunner()
)
```

Create the deployment:

```bash
prefect deployment create ./example-deployment.py
```

In a separate terminal, start the Orion API:

```bash
prefect orion start
```

Then create a flow run for the deployment:

```bash
prefect deployment run my-flow/example
```

You should see output in the Orion API as the flow run is submitted and a container is created.

You can check that the container was run with:

```bash
docker container ls --latest
```

You should see a container with a name matching your flow run name.

## Configuring an image

When you create a deployment with a Docker flow runner, the container image defaults to a Prefect image. This image has the `prefect` package preinstalled.

We ensure that the Prefect and Python versions used to create the deployment are used when the deployment is run. For example, if using Prefect `2.0a7` and Python `3.8`, we will generate the image tag `prefecthq/prefect:2.0a7-python3.8`.

Often, you will want to use your own Docker image to run your flow. This image may have additional requirements preinstalled.

To use a custom image, provide the `image` setting:

```python
from prefect.flow_runners import DockerFlowRunner

DockerFlowRunner(image="my-custom-tag")
```

When using a custom image, you must have the `prefect` Python package installed and available from the default `python` command. We recommend deriving your image from a Prefect base image e.g. `prefecthq/prefect:2.0a7-python3.8`.

### Adding requirements to the default image

If you have some Python dependencies, but do not want to build your own image, our default image supports dynamic installation with `pip`.

To use this feature, provide the environment variable `EXTRA_PIP_PACKAGES`:

```python
from prefect.flow_runners import DockerFlowRunner

DockerFlowRunner(env={"EXTRA_PIP_PACKAGES": "my-extra-package1 my-extra-package2"})
```

## Using Docker with a standalone agent

Since the created Docker container must be able to communicate with the API, the ephemeral API cannot be used with the Docker flow runner.

When you run the standadlone API with `prefect orion start`, an agent is included by default. When run with the `--no-agent` flag, the agent will not be run alongside the API.

The agent can be run standalone with `prefect agent start`. However, if you start the agent without giving it an API URL, it will run an ephemeral server. If this agent attempts to submit a flow run using the Docker flow runner, it will immediately fail.

To connect to your hosted API, provide the `PREFECT_ORION_HOST` environment variable:

```bash
PREFECT_ORION_HOST="http://127.0.0.1:4200/api/" prefect agent start
```
