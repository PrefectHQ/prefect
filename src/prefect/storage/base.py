import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, List, Dict

import prefect
from prefect import config
from prefect.engine.result import Result
from prefect.storage import _healthcheck
from prefect.utilities import logging as prefect_logging

if TYPE_CHECKING:
    from prefect import Flow


class Storage(metaclass=ABCMeta):
    """
    Base interface for Storage objects. All kwargs present in this base class are valid on storage
    subclasses.

    Args:
        - result (Result, optional): a default result to use for
            all flows which utilize this storage class
        - secrets (List[str], optional): a list of Prefect Secrets which will be used to
            populate `prefect.context` for each flow run.  Used primarily for providing
            authentication credentials.
        - labels (List[str], optional): a list of labels to associate with this `Storage`.
        - add_default_labels (bool): If `True`, adds the storage specific default label (if
            applicable) to the storage labels. Defaults to the value specified in the
            configuration at `flows.defaults.storage.add_default_labels`.
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
    """

    def __init__(
        self,
        result: Result = None,
        secrets: List[str] = None,
        labels: List[str] = None,
        add_default_labels: bool = None,
        stored_as_script: bool = False,
    ) -> None:
        self.result = result
        self.secrets = secrets or []
        self.stored_as_script = stored_as_script

        self.flows = {}  # type: Dict[str, str]
        self._flows = {}  # type: Dict[str, Flow]

        self._labels = labels or []
        if add_default_labels is None:
            self.add_default_labels = config.flows.defaults.storage.add_default_labels
        else:
            self.add_default_labels = add_default_labels

    @property
    def labels(self) -> List[str]:
        """
        Concatenates user provided labels and optionally the storage's
        default labels.
        """
        if not self.add_default_labels:
            return self._labels

        all_labels = set(self._labels)
        all_labels.update(self.default_labels)

        return list(all_labels)

    @property
    def default_labels(self) -> List[str]:
        """
        Holds the default storage labels for a given storage.
        """
        return []

    def __repr__(self) -> str:
        return "<Storage: {}>".format(type(self).__name__)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        raise NotImplementedError()

    @abstractmethod
    def add_flow(self, flow: "Flow") -> str:
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
        Name of the storage object.  Can be overriden.
        """
        return type(self).__name__

    @property
    def logger(self) -> "logging.Logger":
        """
        Prefect logger.
        """
        return prefect_logging.get_logger(type(self).__name__)

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    def build(self) -> "Storage":
        """
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
        """
        self.run_basic_healthchecks()

        return self

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

        _healthcheck.result_check(self._flows.values(), quiet=True)  # type: ignore
