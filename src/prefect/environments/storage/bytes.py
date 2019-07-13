from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Union

import cloudpickle

import prefect
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Bytes(Storage):
    """
    Bytes Storage class, mainly used for testing.  This class represents the Storage
    interface for Flows stored directly as bytes.

    The main difference between this class and `Memory` storage is that `Bytes`
    can be serialized and deserialized while preserving all relevant information.
    """

    def __init__(self) -> None:
        self.flows = dict()  # type: Dict[str, bytes]
        super().__init__()

    def get_flow(self, flow_location: str) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a flow location is simply a Flow's name

        Returns:
            - Flow: the requested flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if not flow_location in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_bytes = self.flows[flow_location]
        return cloudpickle.loads(flow_bytes)

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )
        self.flows[flow.name] = cloudpickle.dumps(flow)
        return flow.name

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
        return self
