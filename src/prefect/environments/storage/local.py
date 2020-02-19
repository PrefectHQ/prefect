import os
import socket
from typing import TYPE_CHECKING, Any, Dict, List

from slugify import slugify

import prefect
from prefect.engine.result_handlers import LocalResultHandler
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Local(Storage):
    """
    Local storage class.  This class represents the Storage
    interface for Flows stored as bytes in the local filesystem.

    Note that if you register a Flow with Prefect Cloud using this storage,
    your flow's environment will automatically be labeled with your machine's hostname.
    This ensures that only agents that are known to be running on the same filesystem can
    run your flow.

    Args:
        - directory (str, optional): the directory the flows will be stored in;
            defaults to `~/.prefect/flows`.  If it doesn't already exist, it will be
            created for you.
        - validate (bool, optional): a boolean specifying whether to validate the
            provided directory path; if `True`, the directory will be converted to an
            absolute path and created.  Defaults to `True`
    """

    def __init__(self, directory: str = None, validate: bool = True) -> None:
        directory = directory or os.path.join(prefect.config.home_dir, "flows")
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]

        if validate:
            abs_directory = os.path.abspath(os.path.expanduser(directory))
            if not os.path.exists(abs_directory):
                os.makedirs(abs_directory)
        else:
            abs_directory = directory

        self.directory = abs_directory
        result_handler = LocalResultHandler(self.directory, validate=validate)
        super().__init__(result_handler=result_handler)

    @property
    def labels(self) -> List[str]:
        return [socket.gethostname()]

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

        return prefect.core.flow.Flow.load(flow_location)

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
        flow_location = flow.save(flow_location)
        self.flows[flow.name] = flow_location
        self._flows[flow.name] = flow
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
        self.run_basic_healthchecks()
        return self
