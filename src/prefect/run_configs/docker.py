from typing import Iterable

from prefect.run_configs.base import RunConfig


class DockerRun(RunConfig):
    """Configure a flow-run to run as a Docker container.

    Args:
        - image (str, optional): The image to use
        - env (dict, optional): Additional environment variables to set in the
            container
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work
        - ports (Iterable[int], optional): an iterable of ports to pass to the
            Docker Agent which are used to expose container ports.
        - host_config (dict, optional): A dictionary or runtime arguments to pass to
            the Docker Agent. See link below for options.
            https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config

    Examples:

    Use the defaults set on the agent:

    ```python
    flow.run_config = DockerRun()
    ```

    Set an environment variable in the flow run process:

    ```python
    flow.run_config = DockerRun(env={"SOME_VAR": "value"})
    ```
    """

    def __init__(
        self,
        *,
        image: str = None,
        env: dict = None,
        labels: Iterable[str] = None,
        ports: Iterable[int] = None,
        host_config: dict = None,
    ) -> None:
        super().__init__(env=env, labels=labels)
        self.image = image
        self.host_config = host_config
        self.ports = ports
