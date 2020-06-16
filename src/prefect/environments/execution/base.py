"""
Environments are JSON-serializable objects that fully describe how to run a flow. Serialization
schemas are contained in `prefect.serialization.environment.py`.

Different Environment objects correspond to different computation environments. Environments
that are written on top of a type of infrastructure also define how to set up and execute
that environment. e.g. the `DaskKubernetesEnvironment` is an environment which
runs a flow on Kubernetes using the `dask-kubernetes` library.
"""

from typing import Any, Callable, Iterable, TYPE_CHECKING

import prefect
from prefect.client import Client
from prefect.utilities import logging
from prefect.utilities.graphql import with_args

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class Environment:
    """
    Base class for Environments.

    An environment is an object that can be instantiated in a way that makes it possible to
    call `environment.setup()` to stand up any required static infrastructure and
    `environment.execute()` to execute the flow inside this environment.

    The `setup` and `execute` functions of an environment require a Prefect Flow object.

    Args:
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
    """

    def __init__(
        self,
        labels: Iterable[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        self.labels = set(labels) if labels else set()
        self.on_start = on_start
        self.on_exit = on_exit
        self.metadata = metadata or {}
        self.logger = logging.get_logger(type(self).__name__)

    def __repr__(self) -> str:
        return "<Environment: {}>".format(type(self).__name__)

    @property
    def dependencies(self) -> list:
        return []

    def setup(self, flow: "Flow") -> None:
        """
        Sets up any infrastructure needed for this environment

        Args:
            - flow (Flow): the Flow object
        """

    def execute(self, flow: "Flow", **kwargs: Any) -> None:
        """
        Executes the flow for this environment from the storage parameter

        Args:
            - flow (Flow): the Flow object
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """

    def serialize(self) -> dict:
        """
        Returns a serialized version of the Environment

        Returns:
            - dict: the serialized Environment
        """
        schema = prefect.serialization.environment.EnvironmentSchema()
        return schema.dump(self)

    def run_flow(self) -> None:
        """
        Run the flow using the default executor

        Raises:
            - ValueError: if no `flow_run_id` is found in context
        """
        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import (
                get_default_flow_runner_class,
                get_default_executor_class,
            )

            flow_run_id = prefect.context.get("flow_run_id")

            if not flow_run_id:
                raise ValueError("No flow run ID found in context.")

            query = {
                "query": {
                    with_args("flow_run", {"where": {"id": {"_eq": flow_run_id}}}): {
                        "flow": {"name": True, "storage": True,},
                    }
                }
            }

            client = Client()
            result = client.graphql(query)
            flow_run = result.data.flow_run[0]

            flow_data = flow_run.flow
            storage_schema = prefect.serialization.storage.StorageSchema()
            storage = storage_schema.load(flow_data.storage)

            ## populate global secrets
            secrets = prefect.context.get("secrets", {})
            for secret in storage.secrets:
                secrets[secret] = prefect.tasks.secrets.PrefectSecret(name=secret).run()

            with prefect.context(secrets=secrets):
                flow = storage.get_flow(storage.flows[flow_data.name])
                runner_cls = get_default_flow_runner_class()
                if hasattr(self, "executor_kwargs"):
                    executor_cls = get_default_executor_class()(**self.executor_kwargs)  # type: ignore
                else:
                    executor_cls = get_default_executor_class()
                runner_cls(flow=flow).run(executor=executor_cls)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()
