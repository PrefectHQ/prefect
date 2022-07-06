from typing_extensions import Literal

from prefect.infrastructure.base import Infrastructure


class DockerContainer(Infrastructure):
    type: Literal["docker-container"] = "docker-container"
