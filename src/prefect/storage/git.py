import os

from typing import TYPE_CHECKING, Any

from prefect.client import Secret
from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file
from prefect.utilities.git import TemporaryGitRepo

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Git(Storage):
    """
    Git storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a git repository.

    This class represents a mapping of flow name to file paths contained in the git repo,
    meaning that all flow files should be pushed independently.

    A typical workflow using this storage type might look like the following:

    - Compose flow `.py` file where flow has Git storage:

    ```python
    flow = Flow("my-flow")
    flow.storage = Git(repo="my/repo", flow_path="/flows/flow.py", repo_host="github.com")
    ```

    - Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

    - Call `prefect register -f flow.py` to register this flow with Git storage.

    Args:
        - flow_path (str): A file path pointing to a .py file containing a flow
        - repo (str, optional): The name of a git repository to store this Flow.
            If not provided, the repo must be set using a secret. See `git_clone_url_secret_name`.
        - repo_host (str, optional): The site hosting the repo. Defaults to 'github.com'
        - flow_name (str, optional): A specific name of a flow to extract from a file.
            If not set then the first flow object retrieved from file will be returned.
        - git_token_secret_name (str, optional): The name of the Prefect Secret containing
            an access token for the repo. Defaults to None
        - git_token_username (str, optional): the username associated with git access token,
            if not provided it will default to repo owner
        - git_clone_url_secret_name (str, optional): the name of the Prefect Secret specifying
            the exact git url to clone, if provided it will override repo, repo_host,
            git_token_secret_name, `git_token_username`, `use_ssh`, and `format_access_token`
            parameters
        - branch_name (str, optional): branch name, if not specified and `tag` and `commit_sha`
            not specified, repo default branch latest commit will be used
        - tag (str, optional): tag name, if not specified and `branch_name` and `commit_sha`
            not specified, repo default branch latest commit will be used
        - commit (str, optional): a commit SHA-1 value, if not specified and `branch_name`
            and `tag` not specified, repo default branch latest commit will be used
        - clone_depth (int): the number of history revisions in cloning, defaults to 1
        - use_ssh (bool): if True, cloning will use ssh. Ssh keys must be correctly
            configured in the environment for this to work
        - format_access_token (bool): if True, the class will attempt to format access tokens
            for common git hosting sites
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        flow_path: str,
        repo: str = None,
        repo_host: str = "github.com",
        flow_name: str = None,
        git_token_secret_name: str = None,
        git_token_username: str = None,
        git_clone_url_secret_name: str = None,
        branch_name: str = None,
        tag: str = None,
        commit: str = None,
        clone_depth: int = 1,
        use_ssh: bool = False,
        format_access_token: bool = True,
        **kwargs: Any,
    ) -> None:
        if sum([bool(x) for x in (branch_name, tag, commit)]) > 1:
            raise ValueError(
                "Please provide only one of the following parameters: `branch_name`, `tag`, `commit`"
            )

        if repo is None and git_clone_url_secret_name is None:
            raise ValueError(
                "Either `repo` or `git_clone_url_secret_name` must be provided"
            )

        if use_ssh and git_token_secret_name is not None:
            self.logger.warning(
                "Git Storage initialized with `use_ssh = True` and `git_token_secret_name` provided. "
                "SSH will be used to clone the repository. `git_token_secret_name` will be ignored"
            )

        if git_clone_url_secret_name and any(
            [
                repo,
                repo_host,
                git_token_secret_name,
                git_token_username,
                use_ssh,
                format_access_token,
            ]
        ):
            self.logger.warning(
                "Git storage initialized with a `git_clone_url_secret_name`. The value of this Secret "
                "will be used to clone the repository, ignoring `repo`, `repo_host`, "
                "`git_token_secret_name`,  `git_token_username`, `use_ssh`, and "
                "`format_access_token`."
            )

        self.flow_path = flow_path
        self.repo = repo
        self.repo_host = repo_host
        self.flow_name = flow_name
        self.git_token_secret_name = git_token_secret_name
        self.git_clone_url_secret_name = git_clone_url_secret_name

        # if not provided, assume the username associated with the token
        # is the organization that owns the repo
        self.git_token_username = (
            git_token_username
            if git_token_username
            else (repo.split("/")[0] if repo else None)
        )

        self.branch_name = branch_name
        self.tag = tag
        self.commit = commit
        self.clone_depth = clone_depth
        self.use_ssh = use_ssh
        self.format_access_token = format_access_token
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

        with TemporaryGitRepo(
            git_clone_url=self.git_clone_url,
            branch_name=self.branch_name,
            tag=self.tag,
            commit=self.commit,
            clone_depth=self.clone_depth,
        ) as temp_repo:
            flow = extract_flow_from_file(
                file_path=os.path.join(temp_repo.temp_dir.name, self.flow_path),
                flow_name=self.flow_name,
            )
        return flow

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
        self.flows[flow.name] = self.flow_path
        self._flows[flow.name] = flow
        return self.flow_path

    @property
    def git_token_secret(self) -> str:
        """
        Get and format the git secret token if it exists
        """
        if self.git_token_secret_name is None:
            return ""

        # get the access token and format it for common git hosts
        access_token = Secret(self.git_token_secret_name).get()
        if self.format_access_token:
            return f"{self.git_token_username}:{access_token}"
        return str(access_token)

    @property
    def git_clone_url(self) -> str:
        """
        Build the git url to clone
        """
        if self.git_clone_url_secret_name:
            return Secret(self.git_clone_url_secret_name).get()  # type: ignore

        if self.use_ssh:
            return f"git@{self.repo_host}:{self.repo}.git"
        return f"https://{self.git_token_secret}@{self.repo_host}/{self.repo}.git"
