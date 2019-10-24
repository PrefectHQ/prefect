from typing import Any, Callable, List

from prefect import config
from prefect.environments.execution import Environment
from prefect.environments.storage import Storage
from prefect.utilities.configuration import set_temporary_config


class RemoteEnvironment(Environment):
    """
    RemoteEnvironment is an environment which takes in information about an executor
    and runs the flow in place using that executor.

    Example:
    ```python
    # using a RemoteEnvironment w/ an existing Dask cluster

    env = RemoteEnvironment(
        executor="prefect.engine.executors.DaskExecutor",
        executor_kwargs={"address": "tcp://dask_scheduler_address"}
    )

    f = Flow("dummy flow", environment=env)
    ```

    Args:
        - executor (str, optional): an importable string to an executor class; defaults
            to `prefect.config.engine.executor.default_class`
        - executor_kwargs (dict, optional): a dictionary of kwargs to be passed to
            the executor; defaults to an empty dictionary
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(
        self,
        executor: str = None,
        executor_kwargs: dict = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
    ) -> None:
        self.executor = executor or config.engine.executor.default_class
        self.executor_kwargs = executor_kwargs or dict()
        super().__init__(labels=labels, on_start=on_start, on_exit=on_exit)

    @property
    def dependencies(self) -> list:
        return []

    def execute(  # type: ignore
        self, storage: "Storage", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Run a flow from the `flow_location` here using the specified executor and
        executor kwargs.

        Args:
            - storage (Storage): the storage object that contains information relating
                to where and how the flow is stored
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """

        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import (
                get_default_executor_class,
                get_default_flow_runner_class,
            )

            # Load serialized flow from file and run it with a DaskExecutor
            flow = storage.get_flow(flow_location)
            with set_temporary_config({"engine.executor.default_class": self.executor}):
                executor = get_default_executor_class()

            executor = executor(**self.executor_kwargs)
            runner_cls = get_default_flow_runner_class()
            runner_cls(flow=flow).run(executor=executor)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()
