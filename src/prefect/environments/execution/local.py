from typing import Any, TYPE_CHECKING

from prefect.environments.execution.base import Environment

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class LocalEnvironment(Environment):
    """
    A LocalEnvironment class for executing a flow in the local process.
    Execution will first attempt to call `get_flow` on the flow's storage object,
    and if that fails it will fall back to `get_env_runner`.  If `get_env_runner` is
    used, the environment variables from this process will be passed.

    Args:
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
    """

    @property
    def dependencies(self) -> list:
        return []

    def execute(self, flow: "Flow", **kwargs: Any) -> None:
        """
        Executes the flow provided to this environment by calling `get_flow` on the
        flow's storage; if that fails, `get_env_runner` will be used with the OS
        environment variables inherited from this process.

        Args:
            - flow (Flow): the Flow object
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """

        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import get_default_flow_runner_class

            runner_cls = get_default_flow_runner_class()
            runner_cls(flow=flow).run(**kwargs)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()
