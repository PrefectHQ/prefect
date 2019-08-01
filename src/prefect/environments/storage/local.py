import os
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Union

import cloudpickle
from slugify import slugify

import prefect
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Local(Storage):
    """
    Local storage class.  This class represents the Storage
    interface for Flows stored as bytes in the local filesystem.

    Args:
        - directory (str, optional): the directory the flows will be stored in;
            defaults to `~/.prefect/flows`.  If it doesn't already exist, it will be
            created for you.
    """

    def __init__(self, directory: str = "~/.prefect/flows") -> None:
        self.flows = dict()  # type: Dict[str, str]
        abs_directory = os.path.abspath(os.path.expanduser(directory))
        if not os.path.exists(abs_directory):
            os.makedirs(abs_directory)
        self.directory = abs_directory
        super().__init__()

    def get_flow(self, flow_location: str) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path where a Flow has been serialized to

        Returns:
            - Flow: the requested flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if not flow_location in self.flows.values():
            raise ValueError("Flow is not contained in this Storage")

        with open(flow_location, "rb") as f:
            flow = cloudpickle.load(f)
        return flow

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for storing a new flow as bytes in the local filesytem.

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

        flow_location = os.path.join(
            self.directory, "{}.prefect".format(slugify(flow.name))
        )
        with open(flow_location, "wb") as f:
            cloudpickle.dump(flow, f)
        self.flows[flow.name] = flow_location
        return flow_location

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
