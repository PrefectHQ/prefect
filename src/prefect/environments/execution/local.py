from typing import Any, Iterable, Callable, TYPE_CHECKING

import prefect
from prefect.environments.execution.base import Environment

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class LocalEnvironment(Environment):
    """
    A LocalEnvironment class for executing a flow in the local process.

    Args:
        - executor (Executor, optional): the executor to run the flow with. If not provided, the
            default executor will be used.
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
    """

    def __init__(
        self,
        executor: "prefect.engine.executors.Executor" = None,
        labels: Iterable[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        if executor is None:
            executor = prefect.engine.get_default_executor_class()()
        elif not isinstance(executor, prefect.engine.executors.Executor):
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

    def execute(self, flow: "Flow", **kwargs: Any) -> None:
        """
        Executes the flow in the local process.

        Args:
            - flow (Flow): the Flow object
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import get_default_flow_runner_class

            runner_cls = get_default_flow_runner_class()
            runner_cls(flow=flow).run(executor=self.executor, **kwargs)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            if self.on_exit:
                self.on_exit()
