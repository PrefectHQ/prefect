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
from prefect.utilities import logging

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
