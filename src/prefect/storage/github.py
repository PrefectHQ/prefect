from typing import TYPE_CHECKING, Any, Dict


from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class GitHub(Storage):
    """
    GitHub storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a GitHub repository.

    This class represents a mapping of flow name to file paths contained in the git repo,
    meaning that all flow files should be pushed independently. A typical workflow using
    this storage type might look like the following:

    - Compose flow `.py` file where flow has GitHub storage:

    ```python
    flow = Flow("my-flow")
    flow.storage = GitHub(repo="my/repo", path="/flows/flow.py")
    ```

    - Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

    - Call `prefect register -f flow.py` to register this flow with GitHub storage.

    Args:
        - repo (str): the name of a GitHub repository to store this Flow
        - path (str, optional): a path pointing to a flow file in the repo
        - ref (str, optional): a commit SHA-1 value or branch name. Defaults to 'master' if not specified
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self, repo: str, path: str = None, ref: str = "master", **kwargs: Any
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]
        self.repo = repo
        self.path = path
        self.ref = ref

        super().__init__(**kwargs)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_location = self.flows[flow_name]

        from github import UnknownObjectException

        repo = self._github_client.get_repo(self.repo)

        try:
            contents = repo.get_contents(flow_location, ref=self.ref)
            decoded_contents = contents.decoded_content
        except UnknownObjectException as exc:
            self.logger.error(
                "Error retrieving file contents from {} on repo {}. Ensure the file exists.".format(
                    flow_location, self.repo
                )
            )
            raise exc

        return extract_flow_from_file(
            file_contents=decoded_contents, flow_name=flow_name
        )

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
        Build the GitHub storage object and run basic healthchecks. Due to this object
        supporting file based storage no files are committed to the repository during
        this step. Instead, all files should be committed independently.

        Returns:
            - Storage: a GitHub object that contains information about how and where
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
    def _github_client(self):  # type: ignore
        from prefect.utilities.git import get_github_client

        return get_github_client()
