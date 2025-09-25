"""
Interface for creating and reading artifacts.
"""
from collections import OrderedDict
import math
import json
from typing import Any, Optional, Dict, Union
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.client.schemas.actions import ArtifactCreate, ArtifactUpdate
from prefect.client.schemas.objects import Artifact as ArtifactResponse
from prefect.context import MissingContextError
from prefect.utilities.context import get_task_and_flow_run_ids


class ArtifactRegistry:
    """
    Registry to track which artifacts contain which ArtifactData objects.
    This avoids circular references while enabling automatic syncing.
    """
    _data_to_artifact: Dict[UUID, 'Artifact'] = {}
    
    @classmethod
    def register(cls, data_id: UUID, artifact: 'Artifact') -> None:
        """Register an ArtifactData object with its containing artifact."""
        cls._data_to_artifact[data_id] = artifact
    
    @classmethod
    def unregister(cls, data_id: UUID) -> None:
        """Unregister an ArtifactData object."""
        cls._data_to_artifact.pop(data_id, None)
    
    @classmethod
    def get_artifact(cls, data_id: UUID) -> Optional['Artifact']:
        """Get the artifact that contains the given ArtifactData object."""
        return cls._data_to_artifact.get(data_id)
    
    @classmethod
    def sync_data(cls, data_id: UUID) -> None:
        """Sync changes for the given ArtifactData object."""
        artifact = cls.get_artifact(data_id)
        if artifact and artifact.id:
            artifact._update()

class ArtifactData(PrefectBaseModel):
    """
    A piece of data intended for human consumption.
    """
    id: UUID = Field(default_factory=uuid4, exclude=True)
    
    def _sync_if_registered(self) -> None:
        """Sync changes if this ArtifactData is registered with an artifact."""
        ArtifactRegistry.sync_data(self.id)

    def _format(self) -> str:
        ...

class Markdown(ArtifactData):
    """
    A piece of markdown intended for human consumption.
    """
    markdown: str

    def update(self, markdown: str) -> None:
        """
        Update the markdown content and automatically sync if registered with an artifact.
        
        Args:
            markdown: New markdown content
        """
        self.markdown = markdown
        self._sync_if_registered()

    def _format(self) -> str:
        return self.markdown

class Link(ArtifactData):
    """
    A link intended for human consumption.
    """
    link: str
    link_text: Optional[str]

    def update(self, link: str, link_text: Optional[str] = None) -> None:
        """
        Update the link content and automatically sync if registered with an artifact.
        
        Args:
            link: New link URL
            link_text: New link text (optional)
        """
        self.link = link
        if link_text is not None:
            self.link_text = link_text
        self._sync_if_registered()

    def _format(self) -> str:
        return f"[{self.link_text}]({self.link})" if self.link_text else f"[{self.link}]({self.link})"

class Progress(ArtifactData):
    """
    A progress indicator intended for human consumption.
    """
    progress: float

    def update(self, progress: float) -> None:
        """
        Update the progress value and automatically sync if registered with an artifact.
        
        Args:
            progress: New progress value (0-100)
        """
        self.progress = progress
        self._sync_if_registered()

    def _format(self) -> float:
        # Ensure progress is between 0 and 100
        min_progress = 0.0
        max_progress = 100.0
        if self.progress < min_progress or self.progress > max_progress:
            self.progress = max(min_progress, min(self.progress, max_progress))

        return self.progress

class Image(ArtifactData):
    """
    An image intended for human consumption.
    """
    image_url: str

    def update(self, image_url: str) -> None:
        """
        Update the image URL and automatically sync if registered with an artifact.
        
        Args:
            image_url: New image URL
        """
        self.image_url = image_url
        self._sync_if_registered()

    def _format(self) -> str:
        return f"![{self.image_url}]({self.image_url})"

class Table(ArtifactData):
    """
    A table intended for human consumption.
    """
    table: Union[dict[str, list[Any]], list[dict[str, Any]], list[list[Any]]]

    def update(self, table: Union[dict[str, list[Any]], list[dict[str, Any]], list[list[Any]]]) -> None:
        """
        Update the table data and automatically sync if registered with an artifact.
        
        Args:
            table: New table data
        """
        self.table = table
        self._sync_if_registered()

    def _format(self) -> str:
        return self._to_markdown_table()
    
    def _to_markdown_table(self) -> str:
        """
        Convert table data to markdown table format.
        Handles dict[str, list[Any]], list[dict[str, Any]], and list[list[Any]] formats.
        """
        if isinstance(self.table, dict):
            # Format: {"col1": [val1, val2], "col2": [val1, val2]}
            return self._dict_to_markdown_table(self.table)
        elif isinstance(self.table, list) and len(self.table) > 0:
            if isinstance(self.table[0], dict):
                # Format: [{"col1": val1, "col2": val2}, {"col1": val1, "col2": val2}]
                return self._list_of_dicts_to_markdown_table(self.table)
            else:
                # Format: [["col1", "col2"], [val1, val2], [val1, val2]]
                return self._list_of_lists_to_markdown_table(self.table)
        else:
            return "Empty table"
    
    def _dict_to_markdown_table(self, table_dict: dict[str, list[Any]]) -> str:
        """Convert dict format to markdown table."""
        if not table_dict:
            return "Empty table"
        
        # Get column names
        columns = list(table_dict.keys())
        
        # Get all values and find max length
        all_values = list(table_dict.values())
        max_rows = max(len(values) for values in all_values) if all_values else 0
        
        # Build table rows
        rows = []
        
        # Header row
        header = "| " + " | ".join(str(col) for col in columns) + " |"
        rows.append(header)
        
        # Separator row
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        rows.append(separator)
        
        # Data rows
        for i in range(max_rows):
            row_data = []
            for col in columns:
                values = table_dict[col]
                value = values[i] if i < len(values) else ""
                row_data.append(str(value))
            row = "| " + " | ".join(row_data) + " |"
            rows.append(row)
        
        return "\n".join(rows)
    
    def _list_of_dicts_to_markdown_table(self, table_list: list[dict[str, Any]]) -> str:
        """Convert list of dicts format to markdown table."""
        if not table_list:
            return "Empty table"
        
        # Get all unique keys from all dictionaries
        all_keys = set()
        for row in table_list:
            all_keys.update(row.keys())
        columns = sorted(list(all_keys))
        
        # Build table rows
        rows = []
        
        # Header row
        header = "| " + " | ".join(str(col) for col in columns) + " |"
        rows.append(header)
        
        # Separator row
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        rows.append(separator)
        
        # Data rows
        for row_dict in table_list:
            row_data = []
            for col in columns:
                value = row_dict.get(col, "")
                row_data.append(str(value))
            row = "| " + " | ".join(row_data) + " |"
            rows.append(row)
        
        return "\n".join(rows)
    
    def _list_of_lists_to_markdown_table(self, table_list: list[list[Any]]) -> str:
        """Convert list of lists format to markdown table."""
        if not table_list:
            return "Empty table"
        
        # Build table rows
        rows = []
        
        # Header row (first row)
        if len(table_list) > 0:
            header = "| " + " | ".join(str(cell) for cell in table_list[0]) + " |"
            rows.append(header)
            
            # Separator row
            separator = "| " + " | ".join("---" for _ in table_list[0]) + " |"
            rows.append(separator)
            
            # Data rows (remaining rows)
            for row in table_list[1:]:
                row_data = "| " + " | ".join(str(cell) for cell in row) + " |"
                rows.append(row_data)
        
        return "\n".join(rows)

class Artifact():
    """
    An artifact is a composable, updatable piece of data intended for human consumption.
    Artifacts can be created inside flow and task runs.
    https://docs.prefect.io/v3/concepts/artifacts
    """

    def __init__(self, key: str, description: Optional[str] = None):
        self.id: Optional[UUID] = None
        self.created: Optional[datetime] = None
        self.updated: Optional[datetime] = None
        self.key: str = key
        self.description: Optional[str] = description
        self.data: OrderedDict[UUID, ArtifactData] = OrderedDict()

    async def _aformat(self) -> str:
        return self._format()

    def _format(self) -> str:
        return "\n\n---\n\n".join([data._format() for data in self.data.values()])

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

    def append(self, data: ArtifactData) -> None:
        # Register the data with this artifact for automatic syncing
        ArtifactRegistry.register(data.id, self)
        self.data[data.id] = data

        if self.id:
            self._update()
        else:
            self._create()
    
    def remove(self, data: ArtifactData) -> None:
        """
        Remove an ArtifactData object from this artifact.
        
        Args:
            data: The ArtifactData object to remove
        """
        if data.id in self.data:
            ArtifactRegistry.unregister(data.id)
            del self.data[data.id]
            if self.id:
                self._update()

    def delete(self) -> None:
        if self.id:
            self._delete()

    def _delete(self, client: Optional[SyncPrefectClient] = None) -> None:
        client = client or get_client(sync_client=True)
        client.delete_artifact(self.id)