import warnings
from typing import Any, Callable, List, TYPE_CHECKING

from prefect import config
from prefect.environments.execution import Environment
from prefect.utilities.configuration import set_temporary_config

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


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
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the
            flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow
            finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this
            environment
    """

    def __init__(
        self,
        executor: str = None,
        executor_kwargs: dict = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        if type(self) is RemoteEnvironment or not type(self).__module__.startswith(
            "prefect."
        ):
            # Only warn if its a subclass not part of prefect, since we don't
            # want to update the code for e.g. `DaskCloudProviderEnvironment`
            warnings.warn(
                "`RemoteEnvironment` is deprecated, please use `LocalEnvironment` instead.",
                stacklevel=2,
            )
        self.executor = executor or config.engine.executor.default_class
        self.executor_kwargs = executor_kwargs or dict()
        super().__init__(
            labels=labels, on_start=on_start, on_exit=on_exit, metadata=metadata
        )

    @property
    def dependencies(self) -> list:
        return []

    def execute(self, flow: "Flow", **kwargs: Any) -> None:  # type: ignore
        """
        Run the provided flow here using the specified executor and executor kwargs.

        Args:
            - flow (Flow): the Flow object
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

            # Run flow with default executor class
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
