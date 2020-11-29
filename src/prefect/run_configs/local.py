import os
from typing import Iterable

from prefect.run_configs.base import RunConfig


class LocalRun(RunConfig):
    """Configure a flow-run to run as a Local Process.

    Args:
        - env (dict, optional): Additional environment variables to set for the process
        - working_dir (str, optional): Working directory in which to start the
            process, must already exist. If not provided, will be run in the
            same directory as the agent.
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

    Examples:

    Use the defaults set on the agent:

    ```python
    flow.run_config = LocalRun()
    ```

    Run in a specified working directory:

    ```python
    flow.run_config = LocalRun(working_dir="/path/to/working-directory")
    ```

    Set an environment variable in the flow run process:

    ```python
    flow.run_config = LocalRun(env={"SOME_VAR": "value"})
    ```
    """

    def __init__(
        self,
        *,
        env: dict = None,
        working_dir: str = None,
        labels: Iterable[str] = None,
    ) -> None:
        super().__init__(labels=labels)
        if working_dir is not None:
            working_dir = os.path.abspath(working_dir)
        self.working_dir = working_dir
        self.env = env
