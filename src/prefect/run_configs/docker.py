from typing import Iterable

from prefect.run_configs.base import RunConfig


class DockerRun(RunConfig):
    """Configure a flow-run to run as a Docker container.

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - image (str, optional): The image to use
        - env (dict, optional): Additional environment variables to set in the
            container
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

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
        self, *, image: str = None, env: dict = None, labels: Iterable[str] = None
    ) -> None:
        super().__init__(labels=labels)
        self.image = image
        self.env = env
