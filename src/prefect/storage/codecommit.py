from typing import TYPE_CHECKING, Any

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
        self.repo = repo
        self.path = path
        self.commit = commit
        self.client_options = client_options

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

    @property
    def _boto3_client(self):  # type: ignore
        from prefect.utilities.aws import get_boto_client

        kwargs = self.client_options or {}
        return get_boto_client(resource="codecommit", credentials=None, **kwargs)
