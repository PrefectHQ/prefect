from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import quote_plus

from prefect.environments.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Bitbucket(Storage):
    """
    Bitbucket storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a Bitbucket repository.
    This class represents a mapping of flow name to file paths contained in the git repo,
    meaning that all flow files should be pushed independently. A typical workflow using
    this storage type might look like the following:
    - Compose flow `.py` file where flow has Bitbucket storage:
    ```python
    flow = Flow("my-flow")
    flow.storage = Bitbucket(project="my/project",repo="my/repo", path="/flows/flow.py", ref="my-branch")
    ```
    - Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.
    - Call `prefect register -f flow.py` to register this flow with Bitbucket storage.
    Args:
        - project (str): Project that the repository will be in.  Not equivalent to a GitHub project;
            required value for all Bitbucket repositories.
        - repo (str): the repository name, with complete taxonomy.
        - host (str, optional): If using Bitbucket server, the server host. If not specified, defaults
            to Bitbucket cloud.
        - path (str, optional): a path pointing to a flow file in the repo
        - ref (str, optional): a commit SHA-1 value or branch name
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        project: str,
        repo: str,
        host: str = None,
        path: str = None,
        ref: str = None,
        **kwargs: Any,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]
        self.project = project
        self.repo = repo
        self.host = host
        self.path = path
        self.ref = ref

        super().__init__(**kwargs)

    @property
    def default_labels(self) -> List[str]:
        return ["bitbucket-flow-storage"]

    def get_flow(self, flow_location: str = None, ref: str = None) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).
        If the Flow is not found an error will be logged and `None` will be returned.
        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path on a repository where a Flow file has been committed. Will use `path` if not
                provided.
            - ref (str, optional): a commit SHA-1 value or branch name. Defaults to 'master' if
                not specified
        Returns:
            - Flow: the requested Flow. Atlassian API retrieves raw, decoded files.
        Raises:
            - ValueError: if the flow is not contained in this storage
            - UnknownObjectException: if the flow file is unable to be retrieved
        """
        if flow_location:
            if flow_location not in self.flows.values():
                raise ValueError("Flow is not contained in this Storage")
        elif self.path:
            flow_location = self.path
        else:
            raise ValueError("No flow location provided")

        ref = ref if ref else (self.ref if self.ref else "master")

        try:
            contents = self._bitbucket_client.get_content_of_file(
                self.project,
                self.repo,
                flow_location,
                at=ref,
            )
        except:
            self.logger.error("Error in retrieve Bitbucket repo files.")
            raise
        # Bitbucket API returns raw files only.
        return extract_flow_from_file(file_contents=contents)

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for storing a new flow as bytes in the local filesytem.
        Args:
            - flow (Flow): a Prefect Flow to add
        Returns:
            - str: the location of the added flow in the repo
        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )

        self.flows[flow.name] = self.path  # type: ignore
        self._flows[flow.name] = flow
        return self.path  # type: ignore

    def build(self) -> "Storage":
        """
        Build the Bitbucket storage object and run basic healthchecks. Due to this object
        supporting file based storage no files are committed to the repository during
        this step. Instead, all files should be committed independently.
        Returns:
            - Storage: a Bitbucket object that contains information about how and where
                each flow is stored
        """
        self.run_basic_healthchecks()

        return self

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    @property
    def _bitbucket_client(self):  # type: ignore
        from prefect.utilities.git import get_bitbucket_client

        return get_bitbucket_client(host=self.host)
