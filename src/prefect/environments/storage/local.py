import os
from pathlib import Path
import socket
from typing import TYPE_CHECKING, Any, Dict, List

from slugify import slugify

import prefect
from prefect.engine.results import LocalResult
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
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        directory: str = None,
        validate: bool = True,
        store_as_pickle: bool = True,
        **kwargs: Any,
    ) -> None:
        directory = directory or os.path.join(prefect.config.home_dir, "flows")
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]

        if validate:
            abs_directory = os.path.abspath(os.path.expanduser(directory))
            if not os.path.exists(abs_directory):
                os.makedirs(abs_directory)
        else:
            abs_directory = directory

        # This needs to be added to the serializers
        self.store_as_pickle = store_as_pickle

        self.directory = abs_directory
        result = LocalResult(self.directory, validate_dir=validate)
        super().__init__(result=result, **kwargs)

    @property
    def default_labels(self) -> List[str]:
        if self.add_default_labels:
            return [socket.gethostname()]
        else:
            return []

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

        if not self.store_as_pickle:
            with open(flow_location, "r") as file:
                contents = file.read()

            exec_vals = {}
            exec(contents, exec_vals)

            # Grab flow name from values loaded via exec
            # This will only work with one flow per file
            for i in exec_vals:
                if isinstance(exec_vals[i], prefect.Flow):
                    return exec_vals[i]
        else:
            # Temporarily moving this value error due to having to save in one file
            # and load in another
            # We need to figure out a good workflow for this
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

        import inspect
        import re

        if not self.store_as_pickle:
            # Grab file off the stack, however this will only work if calling f.serialize(build=True)
            # when calling .add_flow directly it will be [1] level down the stack
            frame = inspect.stack()[2]
            filename = frame[1]
            path_to_flow_file = os.path.abspath(filename)

            # Grab contents of file
            with open(path_to_flow_file, "r") as file:
                contents = file.read()

            # Need to strip out things which could cause circular problems
            # In this case I'm calling serialize(build=True) directly and we don't want this
            contents = re.sub(r"^.*\b(serialize)\b.*$", "", contents, flags=re.M)

            # Save to where flows normally save
            # Could be merged with flow.save where this is ripped from
            path = "{home}/flows".format(home=prefect.context.config.home_dir)
            fpath = Path(os.path.expanduser(path)) / f"{filename}"
            assert fpath is not None  # mypy assert
            fpath.parent.mkdir(exist_ok=True, parents=True)

            flow_location = str(fpath)

            # Write contents to file, should be moved to flow.save somehow
            with open(flow_location, "w") as file:
                file.write(contents)


            # Exec the file to get the flow name
            exec_vals = {}
            exec(contents, exec_vals)

            # Grab flow name from values loaded via exec
            # This will only work with one flow per file
            for i in exec_vals:
                if isinstance(exec_vals[i], prefect.Flow):
                    flow_name = exec_vals[i].name
                    flow = exec_vals[i]
                    break

            # Update self.flows with file path
            self.flows[flow_name] = flow_location
            self._flows[flow_name] = flow
        else:
            # TODO: This logic needs to be moved to build to follow other storage types
            flow_location = os.path.join(
                self.directory, "{}.prefect".format(slugify(flow.name))
            )
            flow_location = flow.save(flow_location)
            self.flows[flow.name] = flow_location
            self._flows[flow.name] = flow

        # Temporary convenience print
        print(flow_location)
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
