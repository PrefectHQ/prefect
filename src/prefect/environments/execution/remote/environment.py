from typing import Any

import cloudpickle

from prefect.environments.execution import Environment
from prefect.environments.storage import Docker
from prefect.utilities import logging
from prefect.utilities.configuration import set_temporary_config


class RemoteEnvironment(Environment):
    """
    RemoteEnvironment is an environment which takes in information around an executor
    and runs the flow in place using that executor.

    Example using a RemoteEnvironment w/ an existing Dask cluster:
    ```
    RemoteEnvironment(
        executor="prefect.engine.executors.DaskExecutor",
        executor_kwargs={"address": "tcp://dask_scheduler_address"}
    )
    ```

    Args:
        - executor (str, optional): an importable string to an executor class; defaults
            to `prefect.engine.executors.SynchronousExecutor`
        - executor_kwargs (dict, optional): a dictionary of kwargs to be passed to
            the executor; defaults to an empty dictionary
    """

    def __init__(
        self,
        executor: str = "prefect.engine.executors.SynchronousExecutor",
        executor_kwargs: dict = dict(),
    ) -> None:
        self.executor = executor
        self.executor_kwargs = executor_kwargs
        self.logger = logging.get_logger("RemoteEnvironment")

    def execute(  # type: ignore
        self, storage: "Docker", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Run a flow from the `flow_location` here using the specified executor and
        executor kwargs.

        Args:
            - storage (Docker): the Docker storage object that contains information relating
                to the image which houses the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """
        if not isinstance(storage, Docker):
            raise TypeError("RemoteEnvironment requires a Docker storage option")

        try:
            from prefect.engine import (
                get_default_executor_class,
                get_default_flow_runner_class,
            )

            # Load serialized flow from file and run it with a DaskExecutor
            with open(flow_location, "rb") as f:
                flow = cloudpickle.load(f)

                with set_temporary_config(
                    {"engine.executor.default_class": self.executor}
                ):
                    executor = get_default_executor_class()

                executor = executor(**self.executor_kwargs)
                runner_cls = get_default_flow_runner_class()
                runner_cls(flow=flow).run(executor=executor)
        except Exception as exc:
            self.logger.error("Unexpected error raised during flow run: {}".format(exc))
            raise exc
