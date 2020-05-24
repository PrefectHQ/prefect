import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, List

import prefect
from prefect.engine.result import Result
from prefect.environments.storage import _healthcheck
from prefect.utilities import logging as prefect_logging

if TYPE_CHECKING:
    import prefect.core.flow


class Storage(metaclass=ABCMeta):
    """
    Base interface for Storage objects.

    Args:
        - result (Result, optional): a default result to use for
            all flows which utilize this storage class
        - secrets (List[str], optional): a list of Prefect Secrets which will be used to populate `prefect.context`
            for each flow run.  Used primarily for providing authentication credentials.
    """

    def __init__(self, result: Result = None, secrets: List[str] = None,) -> None:
        self.result = result
        self.secrets = secrets or []

    @property
    def labels(self) -> List[str]:
        return []

    def __repr__(self) -> str:
        return "<Storage: {}>".format(type(self).__name__)

    def get_env_runner(self, flow_location: str) -> Any:
        """
        Given a `flow_location` within this Storage object, returns something with a
        `run()` method that accepts a collection of environment variables for running the flow;
        for example, to specify an executor you would need to provide
        `{'PREFECT__ENGINE__EXECUTOR': ...}`.

        Args:
            - flow_location (str): the location of a flow within this Storage

        Returns:
            - a runner interface (something with a `run()` method for running the flow)
        """
        raise NotImplementedError()

    def get_flow(self, flow_location: str) -> "prefect.core.flow.Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str): the location of a flow within this Storage

        Returns:
            - Flow: the requested flow
        """
        raise NotImplementedError()

    @abstractmethod
    def add_flow(self, flow: "prefect.core.flow.Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object
        """

    @property
    def name(self) -> str:
        """
        Name of the environment.  Can be overriden.
        """
        return type(self).__name__

    @property
    def logger(self) -> "logging.Logger":
        """
        Prefect logger.
        """
        return prefect_logging.get_logger(type(self).__name__)

    @abstractmethod
    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """

    @abstractmethod
    def build(self) -> "Storage":
        """
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
        """
        raise NotImplementedError()

    def serialize(self) -> dict:
        """
        Returns a serialized version of the Storage object

        Returns:
            - dict: the serialized Storage
        """
        schema = prefect.serialization.storage.StorageSchema()
        return schema.dump(self)

    def run_basic_healthchecks(self) -> None:
        """
        Runs basic healthchecks on the flows contained in this Storage class
        """
        if not hasattr(self, "_flows"):
            return

        _healthcheck.result_check(self._flows.values())  # type: ignore
