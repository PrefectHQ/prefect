import os
from typing import Any, Callable, List

from prefect.environments.execution.base import Environment
from prefect.environments.storage import Storage


class LocalEnvironment(Environment):
    """
    A LocalEnvironment class for executing a flow contained in Storage in the local process.
    Execution will first attempt to call `get_flow` on the storage object, and if that fails it will
    fall back to `get_env_runner`.  If `get_env_runner` is used, the environment variables from this
    process will be passed.

    Args:
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(
        self,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
    ) -> None:
        super().__init__(labels=labels, on_start=on_start, on_exit=on_exit)

    @property
    def dependencies(self) -> list:
        return []

    def execute(self, storage: "Storage", flow_location: str, **kwargs: Any) -> None:
        """
        Executes the flow for this environment from the storage parameter,
        by calling `get_flow` on the storage; if that fails, `get_env_runner` will
        be used with the OS environment variables inherited from this process.

        Args:
            - storage (Storage): the Storage object that contains the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """

        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        env = kwargs.pop("env", dict())
        try:
            runner = storage.get_flow(flow_location)
            runner.run(**kwargs)
        except NotImplementedError:
            env_runner = storage.get_env_runner(flow_location)
            current_env = os.environ.copy()
            current_env.update(env)
            env_runner(env=current_env)
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()
