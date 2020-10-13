from typing import Iterable

from prefect.run_configs.base import RunConfig


class LocalRun(RunConfig):
    """Configure a flow-run to run as a Local Process.

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - env (dict, optional): Additional environment variables to set for the process
        - working_dir (str, optional): Working directory in which to start the
            process, must already exist. If not provided, will be run in the
            same directory as the agent.
        - python_env (str, optional): The python environment to use to run the
            process. Can be either a path to a python executable (on the
            agent), a name or path to a conda environment (prefixed with
            `conda://`), or a path to a virtual environment (prefixed
            with `venv://`). If not provided, defaults to the same Python
            environment running the local agent.
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

    Examples:

    Use the defaults set on the agent:

    ```python
    flow.run_config = LocalRun()
    ```

    Use a conda environment named "prefect":

    ```python
    flow.run_config = LocalRun(python_env="conda://prefect")
    ```

    Use a virtual environment located at `/opt/venvs/prefect`:

    ```python
    flow.run_config = LocalRun(python_env="venv:///opt/vents/prefect")
    ```
    """

    def __init__(
        self,
        *,
        env: dict = None,
        working_dir: str = None,
        python_env: str = None,
        labels: Iterable[str] = None,
    ) -> None:
        super().__init__(labels=labels)
        self.env = env
        self.working_dir = working_dir
        self.python_env = python_env
