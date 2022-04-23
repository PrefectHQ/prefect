import os
import re
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError

import requests
from requests.exceptions import HTTPError as RequestsHTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import prefect
from prefect.client import Secret
from prefect.storage import Storage
from prefect.utilities.storage import extract_flow_from_file


BITBUCKET_CLOUD_RETRY = Retry(
    total=10,
    backoff_factor=0.5,
    status_forcelist=[429],
    # typeshed is out of date with urllib3 and missing `allowed_methods`
    allowed_methods=["HEAD", "GET", "OPTIONS"],  # type: ignore
)

if TYPE_CHECKING:
    import atlassian
    from prefect.core.flow import Flow


class Bitbucket(Storage):
    """
    Bitbucket storage class. This class represents the Storage interface for Flows stored
    in `.py` files in a Bitbucket repository. This is for Bitbucket Server or Bitbucket Cloud.

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
        - project (str): project that the repository will be in.  Not equivalent to a GitHub project;
            required value for all Bitbucket repositories.
        - repo (str): the repository name, with complete taxonomy.
        - workspace (str, optional): the workspace name. Bitbucket cloud only.
        - host (str, optional): the server host. Bitbucket server only.
        - path (str, optional): a path pointing to a flow file in the repo
        - ref (str, optional): a commit SHA-1 value or branch name or tag. If not specified,
            defaults to master branch for the repo.
        - access_token_secret (str, optional): the name of a Prefect secret
            that contains a Bitbucket access token to use when loading flows from
            this storage. Bitbucket Server only
        - cloud_username_secret (str, optional): the name of a Prefect secret that contains a
            Bitbucket username to use when loading flows from this storage. Bitbucket Cloud only.
        - cloud_app_password_secret (str, optional): the name of a Prefect secret that contains a
            Bitbucket app password, from the account associated with the `cloud_username_secret`,
            to use when loading flows from this storage. Bitbucket Cloud only.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        project: str,
        repo: str,
        workspace: str = None,
        host: str = None,
        path: str = None,
        ref: str = None,
        access_token_secret: str = None,
        cloud_username_secret: str = None,
        cloud_app_password_secret: str = None,
        **kwargs: Any,
    ) -> None:
        self.project = project
        self.repo = repo
        self.workspace = workspace
        self.host = host
        self.path = path
        self.ref = ref
        self.access_token_secret = access_token_secret
        self.cloud_username_secret = cloud_username_secret
        self.cloud_app_password_secret = cloud_app_password_secret

        if self.workspace and self.access_token_secret:
            raise ValueError(
                "`access_token_secret` and `workspace` are both set. Setting `workspace` "
                "is only for use with Bitbucket Cloud which uses `cloud_username_secret` "
                "and `cloud_app_password_secret` to provide authentication."
            )

        super().__init__(**kwargs)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """

        return (
            self._get_flow_from_bitbucket_cloud(flow_name)
            if self.workspace
            else self._get_flow_from_bitbucket_server(flow_name)
        )

    def _get_flow_from_bitbucket_cloud(self, flow_name: str) -> "Flow":
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_location = self.flows[flow_name]

        # Use ref attribute if present, defaulting to "master"
        ref = self.ref or "master"

        client = self._get_bitbucket_cloud_client()

        try:

            # Fetch SHA-1 of all branches if ref is not alread a SHA-1 hash
            SHA1_REGEX = r"^[0-9a-f]{40}$"
            if not re.match(SHA1_REGEX, ref):
                branches = client.get(
                    f"repositories/{self.workspace}/{self.repo}/refs/branches"
                )
                branch_hashes = {
                    branch["name"]: branch["target"]["hash"]
                    for branch in branches["values"]
                }

                if ref in branch_hashes:
                    ref = branch_hashes[ref]

            # Fetch SHA-1 of all tags if ref is not alread a SHA-1 hash
            if not re.match(SHA1_REGEX, ref):
                tags = client.get(
                    f"repositories/{self.workspace}/{self.repo}/refs/tags"
                )
                tag_hashes = {
                    tag["name"]: tag["target"]["hash"] for tag in tags["values"]
                }

                if ref in tag_hashes:
                    ref = tag_hashes[ref]

            if not re.match(SHA1_REGEX, ref):
                raise ValueError(
                    f"ref {ref!r} not found in '{self.workspace}/{self.repo}'"
                )

            contents_url = (
                f"repositories/{self.workspace}/{self.repo}/src/{ref}/{flow_location}"
            )
            self.logger.info(f"Downloading flow from Bitbucket cloud - {contents_url}")
            contents = client.get(contents_url)

        except RequestsHTTPError as err:

            if err.response.status_code == 403:
                err_msg = "Access denied to repository. Please check credentials."
            else:
                err_msg = (
                    "Error retrieving contents at "
                    f"{flow_location} in {self.workspace}/{self.project}/{self.repo}@{ref}. "
                    "Please check arguments passed to Bitbucket storage."
                )

            self.logger.error(err_msg)
            raise RuntimeError(err_msg) from err

        return extract_flow_from_file(file_contents=contents, flow_name=flow_name)

    def _get_flow_from_bitbucket_server(self, flow_name: str) -> "Flow":
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_location = self.flows[flow_name]

        # Use ref attribute if present, defaulting to "master"
        ref = self.ref or "master"

        client = self._get_bitbucket_server_client()

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

    def _get_bitbucket_server_client(self) -> "atlassian.Bitbucket":
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

    def _get_bitbucket_cloud_client(self) -> "atlassian.Bitbucket":
        try:
            from atlassian.bitbucket.cloud import Cloud
        except ImportError as exc:
            raise ImportError(
                "Unable to import atlassian, please ensure you have installed the bitbucket extra"
            ) from exc

        cloud_username = (
            Secret(self.cloud_username_secret).get()
            if self.cloud_username_secret is not None
            else os.getenv("BITBUCKET_CLOUD_USERNAME")
        )
        cloud_app_password = (
            Secret(self.cloud_app_password_secret).get()
            if self.cloud_app_password_secret is not None
            else os.getenv("BITBUCKET_CLOUD_APP_PASSWORD")
        )

        # Bitbucket clould api is rate limited, retry at this frequency
        # 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128
        adapter = HTTPAdapter(max_retries=BITBUCKET_CLOUD_RETRY)
        session = requests.Session()
        session.mount("https://", adapter)

        return Cloud(
            username=cloud_username,
            password=cloud_app_password,
            cloud=True,
            session=session,
        )
