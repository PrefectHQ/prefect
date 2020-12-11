from typing import Iterable, Callable, TYPE_CHECKING

import prefect
from prefect.environments.execution.base import Environment, _RunMixin

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class LocalEnvironment(Environment, _RunMixin):
    """
    A LocalEnvironment class for executing a flow in the local process.

    DEPRECATED: Environment based configuration is deprecated, please transition to
    configuring `flow.run_config` instead of `flow.environment`. See
    https://docs.prefect.io/orchestration/flow_config/overview.html for more info.

    Args:
        - executor (Executor, optional): the executor to run the flow with. If not provided, the
            default executor will be used.
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
        executor: "prefect.executors.Executor" = None,
        labels: Iterable[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        if executor is None:
            executor = prefect.engine.get_default_executor_class()()
        elif not isinstance(executor, prefect.executors.Executor):
            raise TypeError(
                f"`executor` must be an `Executor` or `None`, got `{executor}`"
            )
        self.executor = executor
        super().__init__(
            labels=labels, on_start=on_start, on_exit=on_exit, metadata=metadata
        )

    @property
    def dependencies(self) -> list:
        return []

    def execute(self, flow: "Flow") -> None:
        """
        Executes the flow in the local process.

        Args:
            - flow (Flow): the Flow object
        """
        self.run(flow)
