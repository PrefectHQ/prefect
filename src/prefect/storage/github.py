import os
from typing import TYPE_CHECKING, Any

import prefect
from prefect.client import Secret
from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow
    from github import Github


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
        - path (str): a path pointing to a flow file in the repo
        - ref (str, optional): a commit SHA-1 value, tag, or branch name. If not specified,
            defaults to the default branch for the repo.
        - access_token_secret (str, optional): The name of a Prefect secret
            that contains a GitHub access token to use when loading flows from
            this storage.
        - base_url(str, optional): the Github REST api url for the repo. If not specified,
            https://api.github.com is used.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        repo: str,
        path: str,
        ref: str = None,
        access_token_secret: str = None,
        base_url: str = None,
        **kwargs: Any,
    ) -> None:
        self.repo = repo
        self.path = path
        self.ref = ref
        self.access_token_secret = access_token_secret
        self.base_url = base_url

        super().__init__(**kwargs)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        try:
            from github import UnknownObjectException
        except ImportError as exc:
            raise ImportError(
                "Unable to import Github, please ensure you have installed the github extra"
            ) from exc

        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        path = self.flows[flow_name]

        # Log info about the active storage object. Only include `ref` if
        # explicitly set.
        self.logger.info(
            "Downloading flow from GitHub storage - repo: %r, path: %r%s",
            self.repo,
            path,
            f", ref: {self.ref!r}" if self.ref is not None else "",
        )

        client = self._get_github_client()

        try:
            repo = client.get_repo(self.repo)
        except UnknownObjectException:
            self.logger.error(
                "Repo %r not found. Check that it exists (and is spelled correctly), "
                "and that you have configured the proper credentials for accessing it.",
                self.repo,
            )
            raise

        # Use the default branch if unspecified
        ref = self.ref or repo.default_branch

        # Get the current commit sha for this ref
        try:
            commit = repo.get_commit(ref).sha
        except UnknownObjectException:
            self.logger.error("Ref %r not found in repo %r.", ref, self.repo)
            raise

        try:
            contents = repo.get_contents(path, ref=commit)
            assert not isinstance(contents, list)  # mypy
            decoded_contents = contents.decoded_content.decode()
        except UnknownObjectException:
            self.logger.error(
                "File %r not found in repo %r, ref %r", path, self.repo, ref
            )
            raise

        self.logger.info("Flow successfully downloaded. Using commit: %s", commit)

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

    def _get_github_client(self) -> "Github":
        from github import Github

        if self.access_token_secret is not None:
            # If access token secret specified, load it
            access_token = Secret(self.access_token_secret).get()
        else:
            # Otherwise, fallback to loading from local secret or environment variable
            access_token = prefect.context.get("secrets", {}).get("GITHUB_ACCESS_TOKEN")
            if access_token is None:
                access_token = os.getenv("GITHUB_ACCESS_TOKEN")

        if self.base_url:
            return Github(login_or_token=access_token, base_url=self.base_url)
        else:
            return Github(access_token)
