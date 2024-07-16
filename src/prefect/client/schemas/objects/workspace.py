from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
)

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.settings import PREFECT_CLOUD_API_URL, PREFECT_CLOUD_UI_URL


class Workspace(PrefectBaseModel):
    """
    A Prefect Cloud workspace.

    Expected payload for each workspace returned by the `me/workspaces` route.
    """

    account_id: UUID = Field(..., description="The account id of the workspace.")
    account_name: str = Field(..., description="The account name.")
    account_handle: str = Field(..., description="The account's unique handle.")
    workspace_id: UUID = Field(..., description="The workspace id.")
    workspace_name: str = Field(..., description="The workspace name.")
    workspace_description: str = Field(..., description="Description of the workspace.")
    workspace_handle: str = Field(..., description="The workspace's unique handle.")
    model_config = ConfigDict(extra="ignore")

    @property
    def handle(self) -> str:
        """
        The full handle of the workspace as `account_handle` / `workspace_handle`
        """
        return self.account_handle + "/" + self.workspace_handle

    def api_url(self) -> str:
        """
        Generate the API URL for accessing this workspace
        """
        return (
            f"{PREFECT_CLOUD_API_URL.value()}"
            f"/accounts/{self.account_id}"
            f"/workspaces/{self.workspace_id}"
        )

    def ui_url(self) -> str:
        """
        Generate the UI URL for accessing this workspace
        """
        return (
            f"{PREFECT_CLOUD_UI_URL.value()}"
            f"/account/{self.account_id}"
            f"/workspace/{self.workspace_id}"
        )

    def __hash__(self):
        return hash(self.handle)