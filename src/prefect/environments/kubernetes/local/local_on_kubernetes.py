import prefect
from prefect.environments import DockerEnvironment


class LocalOnKubernetesEnvironment(DockerEnvironment):
    """"""

    def __init__(self, registry_url: str = None) -> None:
        DockerEnvironment.__init__(
            self, base_image="python:3.6", registry_url=registry_url
        )

    def execute(self) -> None:
        pass

    def run(self) -> None:
        pass

    def setup(self) -> None:
        pass
