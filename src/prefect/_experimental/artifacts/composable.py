"""
Interface for creating and reading artifacts.
"""
from collections import OrderedDict
from typing import Optional
from datetime import datetime
from uuid import UUID

from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.client.schemas.actions import ArtifactCreate, ArtifactUpdate
from prefect.client.schemas.objects import Artifact as ArtifactResponse
from prefect.context import MissingContextError
from prefect.utilities.context import get_task_and_flow_run_ids
from prefect._experimental.artifacts.components import ArtifactComponent
from prefect._experimental.artifacts._registry import ArtifactRegistry

class Artifact():
    """
    An artifact is a composable piece of data intended for human consumption.
    Artifacts are comprised of ArtifactComponent objects, which can be independently updated.
    Artifacts can only be created inside flow and task runs.
    https://docs.prefect.io/v3/concepts/artifacts

    ```python
    import time

    from prefect import flow
    from prefect._experimental.artifacts.composable import Artifact
    from prefect._experimental.artifacts.components import Markdown

    @flow
    def my_artifact_flow():
        artifact = Artifact(key="my-artifact", description="My artifact")
        markdown = Markdown(markdown="Hello, world!")
        artifact.append(markdown)

        time.sleep(5)

        countdown_markdown = Markdown(markdown="Counting down to zero...")
        artifact.append(countdown_markdown)
        time.sleep(5)

        countdown = 10
        while countdown > 0:
            countdown_markdown.update(markdown=f"Counting down to zero: {countdown}")
            countdown -= 1
            time.sleep(1)
        
        countdown_markdown.update(markdown="Done! Goodbye :)")
        time.sleep(1)

        artifact.remove(countdown_markdown)

    if __name__ == "__main__":
        my_artifact_flow()
    ```
    """

    def __init__(self, key: str, description: Optional[str] = None):
        self.id: Optional[UUID] = None
        self.created: Optional[datetime] = None
        self.updated: Optional[datetime] = None
        self.key: str = key
        self.description: Optional[str] = description
        self.data: OrderedDict[UUID, ArtifactComponent] = OrderedDict()
        self.icon: Optional[str] = None

    def _format(self) -> str:
        return "\n\n---\n\n".join([data._format() for data in self.data.values()])

    async def _acreate(self, client: Optional[PrefectClient] = None) -> None:
        client = client or get_client()

        with client:
            task_run_id, flow_run_id = get_task_and_flow_run_ids()
            if not task_run_id and not flow_run_id:
                raise MissingContextError(
                    "Artifact creation outside of a flow or task run is not permitted."
                )

            response: ArtifactResponse = await client.create_artifact(
                ArtifactCreate(
                    key=self.key,
                    type="markdown",
                    description=self.description,
                    data=self._format(),
                    task_run_id=task_run_id,
                    flow_run_id=flow_run_id,
                )
            )
            self.id = response.id
            self.created = response.created
            self.updated = response.updated


    def _create(self, client: Optional[SyncPrefectClient] = None) -> None:
        client = client or get_client(sync_client=True)

        with client:
            task_run_id, flow_run_id = get_task_and_flow_run_ids()
            if not task_run_id and not flow_run_id:
                raise MissingContextError(
                    "Artifact creation outside of a flow or task run is not permitted."
                )

            response: ArtifactResponse = client.create_artifact(
                ArtifactCreate(
                    key=self.key,
                    type="markdown",
                    description=self.description,
                    data=self._format(),
                    task_run_id=task_run_id,
                    flow_run_id=flow_run_id,
                )
            )
            self.id = response.id
            self.created = response.created
            self.updated = response.updated

    async def _aupdate(self, client: Optional[PrefectClient] = None) -> None:
        client = client or get_client()

        with client:
            task_run_id, flow_run_id = get_task_and_flow_run_ids()
            if not task_run_id and not flow_run_id:
                raise MissingContextError(
                    "Artifact creation outside of a flow or task run is not permitted."
                )

            client.update_artifact(
                artifact_id=self.id,
                artifact=ArtifactUpdate(
                    data=self._format(),
                    description=self.description,
                )
            )

    def _update(self, client: Optional[SyncPrefectClient] = None) -> None:
        client = client or get_client(sync_client=True)

        with client:
            task_run_id, flow_run_id = get_task_and_flow_run_ids()
            if not task_run_id and not flow_run_id:
                raise MissingContextError(
                    "Artifact creation outside of a flow or task run is not permitted."
                )

            client.update_artifact(
                artifact_id=self.id,
                artifact=ArtifactUpdate(
                    data=self._format(),
                    description=self.description,
                )
            )

    async def aappend(self, data: ArtifactComponent) -> None:
        # Register the component with this artifact
        if not self.id:
            await self._create()

        ArtifactRegistry.register_component(data.id, self.id, self)
            
        self.data[data.id] = data

        await self._update()

    def append(self, data: ArtifactComponent) -> None:
        # Register the component with this artifact
        if not self.id:
            self._create()

        ArtifactRegistry.register_component(data.id, self.id, self)
            
        self.data[data.id] = data

        self._update()
    
    def remove(self, data: ArtifactComponent) -> None:
        """
        Remove an ArtifactComponent object from this artifact.
        
        Args:
            data: The ArtifactComponent object to remove
        """
        if data.id in self.data:
            if self.id:
                ArtifactRegistry.unregister_component(data.id, self.id)
            del self.data[data.id]
            if self.id:
                self._update()