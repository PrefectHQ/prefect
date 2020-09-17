# Flow with Docker

Previously we used the local agent to execute flow runs directly on the current host. Now we will use a Docker agent to execute flow runs within Docker containers on the current host.

:::warning Docker Daemon
In order to use the Docker features make sure you have Docker currently running on your machine.
:::

## Persisting Your Flow with Docker Storage

The default Storage object for flows is [Local Storage](/api/latest/environments/storage.html#local) but it is easy to switch to other options such as [Docker Storage](/api/latest/environments/storage.html#docker).

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

If you do specify a registry URL then the image will be pushed to a container registry upon flow registration.

```python
# Docker Hub (docker.io)
flow.storage = Docker(registry_url="<dockerhub_user>/")

# GCR (gcr.io), etc.
flow.storage = Docker(registry_url="gcr.io/<project_id>/")
```

## Running a Docker Agent

Start the Docker Agent to executing Flow Runs scheduled by the Prefect API:

```bash
prefect agent start docker
```

:::tip Runner Token <Badge text="Cloud"/>
This Docker Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `--token <COPIED_RUNNER_TOKEN>`.
:::

For more information on the Docker Agent visit the [documentation](/orchestration/agents/docker.html).
