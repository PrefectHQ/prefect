# -*- coding: utf-8 -*-

import os
from typing import TYPE_CHECKING, Any, Dict, List
import importlib

import prefect
from prefect.engine.results import LocalResult
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class LocalModule(Storage):
    """
    LocalModule storage class.  This class represents the Storage
    interface for Flows stored as scripts or bytes in the local python path.
    Any agent where the flow is accessible via the given python path is able to
    run the registered flow. This Storage method is targeted for workflow 
    libraries downloaded via pip/conda in combination with LocalEvironment 
    execution.
    
    Args:
        - module_path (str): a direct python path to the location of the flow file. 
            For example, if you access your flow via 'from myrepo.workflows import myflow', you
            would set your module_path to 'myrepo.workflows.myflow'. Here, 'myflow' exists as a
            '.py' file when  `stored_as_script=True` (default). Otherwise `stored_as_script=False` 
            will check for a byte file in the module directory. The maintainer of 'myrepo' should
            make this decision. TIP: rather than writting out 'myrepo.workflows.myflow', you can
            also access this string with '__name__' inside the 'myflow.py' script.
        - class_str (str, optional): The variable name of the Flow instance to use if
            `stored_as_script=True`. This is found by looking inside myflow.py script and 
            see what variable name the Flow instance is set as. Defaults to 'flow'.
        - directory (str, optional): the directory the flows Results will be stored in;
            defaults to `~/.prefect/results`.  If it doesn't already exist, it will be
            created for you. This does not include a centralized `~/.prefect/flows` 
            directory like Local storage does.
        - validate (bool, optional): a boolean specifying whether to validate the
            provided directory path; if `True`, the directory will be converted to an
            absolute path and created.  Defaults to `True`
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `True`. If 'False', the byte file will be written in
            and read from the same module directory as the script. 
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """
    
    def __init__(
        self,
        module_path: str,
        class_str: str = 'flow',
        directory: str = None,
        validate: bool = True,
        stored_as_script: bool = True,
        **kwargs: Any
    ) -> None:
        directory = directory or prefect.config.home_dir
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]
        
        self.module_path = module_path
        self.class_str = class_str

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
        return ["localmod-flow-storage"]

    def get_flow(self, flow_location: str = None) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).
        Args:
            - flow_location (str, optional): the location of a flow within this Storage; in this case,
                a python path where a Flow has been serialized to. Will use `path` if not provided.
        Returns:
            - Flow: the requested flow
        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        print("TEST")
        if flow_location:
            if flow_location not in self.flows.values():
                raise ValueError("Flow is not contained in this Storage")
        elif self.module_path:
            flow_location = self.module_path
        else:
            raise ValueError("No flow location provided")
        
        if self.stored_as_script:
            # load the module written as the flow location 
            # Note: flow_location here is the same as self.module_path
            module = importlib.import_module(flow_location)
            # use the class string to grab the flow object instance and return it
            return getattr(module, self.class_str)
        else:
            # TO-DO
            #flow_location = module.__file__ # need to convert the end 'myflow.py' to 'flow-name.prefect'
            #return prefect.core.flow.Flow.load(flow_location)
            raise ValueError("Sorry, stored_as_script=False is not yet supported for this storage.")
            
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
        
        # TO-DO...
        # whether self.stored_as_script is true or not, the path to this directory is the same
        # We don't save the flow to bytes here. This should be done by the library maintainer
        # when using Local storage. However, a dev-friendly feature for this may be added in the future
        
        flow_location = self.module_path
        
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
