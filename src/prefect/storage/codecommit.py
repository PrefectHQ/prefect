from typing import TYPE_CHECKING, Any, Dict

from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class CodeCommit(Storage):
    """
    CodeCommit storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a CodeCommit repository.

    This class represents a mapping of flow name to file paths contained in the git repo,
    meaning that all flow files should be pushed independently. A typical workflow using
    this storage type might look like the following:

    - Compose flow `.py` file where flow has CodeCommit storage:

    ```python
    flow = Flow("my-flow")
    flow.storage = CodeCommit(repo="my/repo", path="/flows/flow.py")
    ```

    - Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

    - Call `prefect register -f flow.py` to register this flow with CodeCommit storage.

    Args:
        - repo (str): the name of a CodeCommit repository to store this Flow
        - path (str, optional): a path pointing to a flow file in the repo
        - commit (str, optional): fully quaified reference that identifies the commit
          that contains the file. For example, you can specify a full commit ID, a tag,
          a branch name, or a reference such as refs/heads/master. If none is provided,
          the head commit is used
        - client_options (dict, optional): Additional options for the `boto3` client.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        repo: str,
        path: str = None,
        commit: str = None,
        client_options: dict = None,
        **kwargs: Any
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]
        self.repo = repo
        self.path = path
        self.commit = commit
        self.client_options = client_options

        super().__init__(**kwargs)

    def get_flow(self, flow_location: str = None) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).
        If the Flow is not found an error will be logged and `None` will be returned.

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path on a repository where a Flow file has been committed. Will use `path` if not
                provided.

        Returns:
            - Flow: the requested Flow

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

        client = self._boto3_client

        try:
            file_contents = client.get_file(
                repositoryName=self.repo,
                commitSpecifier=self.commit,
                filePath=flow_location,
            )["fileContent"]
            decoded_contents = file_contents.decode("utf-8")
        except Exception as exc:
            self.logger.error(
                "Error retrieving file contents from {} on repo {}. Ensure the file exists.".format(
                    flow_location, self.repo
                )
            )
            raise exc

        return extract_flow_from_file(file_contents=decoded_contents)

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
        Build the CodeCommit storage object and run basic healthchecks. Due to this object
        supporting file based storage no files are committed to the repository during
        this step. Instead, all files should be committed independently.

        Returns:
            - Storage: a CodeCommit object that contains information about how and where
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
    def _boto3_client(self):  # type: ignore
        from prefect.utilities.aws import get_boto_client

        kwargs = self.client_options or {}
        return get_boto_client(
            resource="codecommit", credentials=None, use_session=False, **kwargs
        )
