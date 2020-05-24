"""
Collection of tasks for orchestrating Docker images and containers.

*Note*: If running these tasks from inside of a docker container itself there are some extra
requirements needed for that to work. The container needs to be able to talk to a Docker
server. There are a few ways to accomplish this:

1. Use a base image that has Docker installed and running
    (e.g. https://hub.docker.com/_/docker)
2. Installing the Docker CLI in the base image
3. Talking to an outside (but accessible) Docker API and providing it to the tasks'
    `docker_server_url` parameter

It may also help to run your container (which will run the Prefect Docker tasks) with
extra privileges. (e.g. --privileged=true) and then installing Docker in the container.
"""

from prefect.tasks.docker.images import (
    BuildImage,
    ListImages,
    PullImage,
    PushImage,
    RemoveImage,
    TagImage,
)

from prefect.tasks.docker.containers import (
    CreateContainer,
    GetContainerLogs,
    ListContainers,
    StartContainer,
    StopContainer,
    RemoveContainer,
    WaitOnContainer,
)
