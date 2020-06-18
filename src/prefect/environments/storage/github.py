import io
from typing import TYPE_CHECKING, Any, Dict, List

import cloudpickle
import pendulum
from slugify import slugify

import prefect
from prefect.engine.results import S3Result
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class GitHub(Storage):
    """
    GitHub storage class
    """

    def __init__(
        self, repo: str, **kwargs: Any
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]
        self.repo = repo

        super().__init__(**kwargs)

    @property
    def default_labels(self) -> List[str]:
        return ["github-flow-storage"]

    def get_flow(self, file: str) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).
        If the Flow is not found an error will be logged and `None` will be returned.

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path where a Flow has been serialized to

        Returns:
            - Flow: the requested Flow

        Raises:
            - ValueError: if the Flow is not contained in this storage
            - botocore.ClientError: if there is an issue downloading the Flow from S3
        """
        repo = self._github_client.get_repo(self.repo)

        contents = repo.get_contents(file)
        f = contents.decoded_content

        exec_vals = {}
        exec(f, exec_vals)

        # Grab flow name from values loaded via exec
        # This will only work with one flow per file
        for i in exec_vals:
            if isinstance(exec_vals[i], prefect.Flow):
                return exec_vals[i]
        # return cloudpickle.loads(output)

    def add_flow(self, file: str, file_path: str) -> str:
        """
        Method for storing a new flow as bytes in the local filesytem.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """
        if file in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    file
                )
            )

        # the file name should be able to be specified or we default to the name of the original .py file
        self.flows[file] = file_path
        return file

    def build(self) -> "Storage":
        """
        Build the S3 storage object by uploading Flows to an S3 bucket. This will upload
        all of the flows found in `storage.flows`. If there is an issue uploading to the
        S3 bucket an error will be logged.

        Returns:
            - Storage: an S3 object that contains information about how and where
                each flow is stored

        Raises:
            - botocore.ClientError: if there is an issue uploading a Flow to S3
        """
        self.run_basic_healthchecks()

        for file, file_path in self.flows.items():
            repo = self._github_client.get_repo(self.repo)
            # try:
                # need to figure this out
                # repo.get_contents(file)
                # need to update
            # except:
                # Doesn't exist
            with open(file_path, "r") as f:
                content = f.read()
            repo.create_file(path=file, content=content, message="I am flow")

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
        from github import Github
        import os

        # We should have some prefect secret defaults for this
        # add support for user/pass/access_token and github enterprise
        return Github(os.getenv("ACCESS_TOKEN"))
