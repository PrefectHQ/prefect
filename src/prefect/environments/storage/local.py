import os
import socket
from typing import TYPE_CHECKING, Any, Dict, List

from slugify import slugify

import prefect
from prefect.engine.results import LocalResult
from prefect.environments.storage import Storage
from prefect.utilities.storage import extract_flow_from_file, extract_flow_from_module

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
        - path (str, optional): a direct path to the location of the flow file if
            `stored_as_script=True`, otherwise this path will be used when storing the serialized,
            pickled flow. If `stored_as_script=True`, the direct path may be a file path
            (such as 'path/to/myflow.py') or a direct python path (such as 'myrepo.mymodule.myflow')
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        directory: str = None,
        validate: bool = True,
        path: str = None,
        stored_as_script: bool = False,
        **kwargs: Any,
    ) -> None:
        directory = directory or os.path.join(prefect.config.home_dir, "flows")
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]

        self.path = path

        if validate:
            abs_directory = os.path.abspath(os.path.expanduser(directory))
            if not os.path.exists(abs_directory):
                os.makedirs(abs_directory)
        else:
            abs_directory = directory

        self.directory = abs_directory
        result = LocalResult(self.directory, validate_dir=validate)
        super().__init__(result=result, stored_as_script=stored_as_script, **kwargs)

    @property
    def default_labels(self) -> List[str]:
        if self.add_default_labels:
            return [socket.gethostname()]
        else:
            return []

    def get_flow(self, flow_location: str = None) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str, optional): the location of a flow within this Storage; in this case,
                a file path or python path where a Flow has been serialized to. Will use `path`
                if not provided.

        Returns:
            - Flow: the requested flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if flow_location:
            if flow_location not in self.flows.values():
                raise ValueError("Flow is not contained in this Storage")
        elif self.path:
            flow_location = self.path
        else:
            raise ValueError("No flow location provided")

        # check if the path given is a file path
        try:
            if os.path.isfile(flow_location):
                if self.stored_as_script:
                    return extract_flow_from_file(file_path=flow_location)
                else:
                    return prefect.core.flow.Flow.load(flow_location)
            # otherwise the path is given in the module format
            else:
                return extract_flow_from_module(module_str=flow_location)
        except Exception:
            self.logger.exception(f"Failed to load Flow from {flow_location}")
            raise

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

        if self.stored_as_script:
            if not self.path:
                raise ValueError(
                    "A `path` must be provided to show where flow `.py` file is stored."
                )
            flow_location = self.path
        else:
            if self.path:
                flow_location = self.path
            else:
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
