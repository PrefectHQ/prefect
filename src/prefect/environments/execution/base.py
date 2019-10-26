"""
Environments are JSON-serializable objects that fully describe how to run a flow. Serialization
schemas are contained in `prefect.serialization.environment.py`.

Different Environment objects correspond to different computation environments. Environments
that are written on top of a type of infrastructure also define how to set up and execute
that environment. e.g. the `DaskKubernetesEnvironment` is an environment which
runs a flow on Kubernetes using the `dask-kubernetes` library.

Some of the information that the environment requires to run a flow -- such as the flow
itself -- may not available when the Environment class is instantiated. Therefore, Environments
are accompanied with a Storage objects to specify how and where the flow is stored. For example,
the `DaskKubernetesEnvironment` requires the flow to be stored in a `Docker` storage object.
"""

from typing import Any, Callable, Iterable

import prefect
from prefect.environments.storage import Storage
from prefect.utilities import logging


class Environment:
    """
    Base class for Environments.

    An environment is an object that can be instantiated in a way that makes it possible to
    call `environment.setup()` to stand up any required static infrastructure and
    `environment.execute()` to execute the flow inside this environment.

    The `setup` and `execute` functions of an environment require a Prefect Storage object which
    specifies how and where the flow is stored.

    Args:
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(
        self,
        labels: Iterable[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
    ) -> None:
        self.labels = set(labels) if labels else set()
        self.on_start = on_start
        self.on_exit = on_exit
        self.logger = logging.get_logger(type(self).__name__)

    def __repr__(self) -> str:
        return "<Environment: {}>".format(type(self).__name__)

    @property
    def dependencies(self) -> list:
        return []

    def setup(self, storage: "Storage") -> None:
        """
        Sets up any infrastructure needed for this environment

        Args:
            - storage (Storage): the Storage object that contains the flow
        """
        pass

    def execute(self, storage: "Storage", flow_location: str, **kwargs: Any) -> None:
        """
        Executes the flow for this environment from the storage parameter

        Args:
            - storage (Storage): the Storage object that contains the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """
        pass

    def serialize(self) -> dict:
        """
        Returns a serialized version of the Environment

        Returns:
            - dict: the serialized Environment
        """
        schema = prefect.serialization.environment.EnvironmentSchema()
        return schema.dump(self)
