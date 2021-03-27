import os
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError

import requests

import prefect
from prefect.client import Secret
from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    import atlassian
    from prefect.core.flow import Flow


class Bitbucket(Storage):
    """
    Bitbucket storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a Bitbucket repository. This is for Bitbucket Server only.

    This class represents a mapping of flow name to file paths contained in the git repo,
    meaning that all flow files should be pushed independently. A typical workflow using
    this storage type might look like the following:

    - Compose flow `.py` file where flow has Bitbucket storage:

    ```python
    flow = Flow("my-flow")
    flow.storage = Bitbucket(
        project="my.project", repo="my.repo", path="/flows/flow.py", ref="my-branch"
    )
    ```

    - Push this `flow.py` file to the `my.repo` repository under `/flows/flow.py` inside "my.project"
        project.

    - Call `prefect register -f flow.py` to register this flow with Bitbucket storage.

    Args:
        - project (str): Project that the repository will be in.  Not equivalent to a GitHub project;
            required value for all Bitbucket repositories.
        - repo (str): the repository name, with complete taxonomy.
        - host (str, optional): If using Bitbucket server, the server host. If not specified, defaults
            to Bitbucket cloud.
        - path (str, optional): a path pointing to a flow file in the repo
        - ref (str, optional): a commit SHA-1 value or branch name
        - access_token_secret (str, optional): The name of a Prefect secret
            that contains a Bitbucket access token to use when loading flows from
            this storage.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        project: str,
        repo: str,
        host: str = None,
        path: str = None,
        ref: str = None,
        access_token_secret: str = None,
        **kwargs: Any,
    ) -> None:
        self.project = project
        self.repo = repo
        self.host = host
        self.path = path
        self.ref = ref
        self.access_token_secret = access_token_secret

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

        # Use ref attribute if present, defaulting to "master"
        ref = self.ref or "master"

        client = self._get_bitbucket_client()

        try:
            contents = client.get_content_of_file(
                self.project,
                self.repo,
                flow_location,
                at=ref,
            )
        except HTTPError as err:
            if err.code == 401:
                self.logger.error(
                    "Access denied to repository. Please check credentials."
                )
                raise
            elif err.code == 404:
                self.logger.error(
                    "Invalid address. Check that host, project, and repository are correct."
                )
                raise
            else:
                self.logger.error(
                    f"Error retrieving contents at {flow_location} in {self.repo}@{ref}. "
                    "Please check arguments passed to Bitbucket storage and verify project exists."
                )
                raise

        return extract_flow_from_file(file_contents=contents, flow_name=flow_name)

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

    def _get_bitbucket_client(self) -> "atlassian.Bitbucket":
        try:
            from atlassian import Bitbucket
        except ImportError as exc:
            raise ImportError(
                "Unable to import atlassian, please ensure you have installed the bitbucket extra"
            ) from exc

        if self.access_token_secret is not None:
            # If access token secret specified, load it
            access_token = Secret(self.access_token_secret).get()
        else:
            # Otherwise, fallback to loading from local secret or environment variable
            access_token = prefect.context.get("secrets", {}).get(
                "BITBUCKET_ACCESS_TOKEN"
            )
            if access_token is None:
                access_token = os.getenv("BITBUCKET_ACCESS_TOKEN")

        host = "https://bitbucket.org" if self.host is None else self.host

        session = requests.Session()
        if access_token is None:
            session.headers["Authorization"] = "Bearer "
        else:
            session.headers["Authorization"] = "Bearer " + access_token
        return Bitbucket(host, session=session)
