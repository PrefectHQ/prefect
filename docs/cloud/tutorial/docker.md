# Cloud Flow with Docker

Previously we used the Local Agent to execute Flow Runs directly on the current host. Now we will use a Docker Agent to execute Flow Runs within Docker containers on the current host.

:::warning Docker Daemon
In order to use the Docker features make sure you have Docker currently running on your machine.
:::

## Persisting Your Flow with Docker Storage

The default Storage object for Flows is [Local Storage](/api/unreleased/environments/storage.html#local) but it is easy to switch to other options such as [Docker Storage](/api/unreleased/environments/storage.html#docker).

```python
import prefect
from prefect import task, Flow
from prefect.environments.storage import Docker

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello, Docker!")

flow = Flow("hello-docker", tasks=[hello_task])

flow.storage = Docker()

flow.register(project_name="Hello, World!")
```

### Pushing to a Registry

Docker Storage accepts an optional keyword argument `registry_url` if this is not specified then the Docker image that is built will only exist on the machine it was built on.

If you do specify a registry URL then the image will be pushed to a container registry upon Flow registration.

```python
flow.storage = Docker(registry_url="docker.io/<dockerhub_user>/<dockerhub_repo>")
```

## Running a Docker Agent

Start the Docker Agent to executing Flow Runs scheduled by Cloud:

```bash
prefect agent start docker
```

:::tip Runner Token
This Docker Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `--token <COPIED_RUNNER_TOKEN>`.
:::

For more information on the Docker Agent visit the [documentation](/cloud/agent/docker.html).
