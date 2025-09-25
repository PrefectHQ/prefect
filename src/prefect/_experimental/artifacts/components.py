"""
Interface for creating and reading artifacts.
"""
from typing import Any, Optional, Union
from uuid import UUID, uuid4

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._experimental.artifacts._registry import ArtifactRegistry

class ArtifactComponent(PrefectBaseModel):
    """
    A piece of data intended for human consumption.
    """
    id: UUID = Field(default_factory=uuid4, exclude=True)
    
    def _sync_if_registered(self) -> None:
        """Sync changes if this ArtifactComponent is registered with an artifact."""
        if ArtifactRegistry.is_registered(self.id):
            # Get all artifacts that contain this component and sync them
            artifact_ids = ArtifactRegistry.get_artifact_ids(self.id)
            for artifact_id in artifact_ids:
                ArtifactRegistry.sync_artifact(artifact_id)

    async def _sync_if_registered_async(self) -> None:
        """Sync changes if this ArtifactComponent is registered with an artifact."""
        if ArtifactRegistry.is_registered(self.id):
            # Get all artifacts that contain this component and sync them
            artifact_ids = ArtifactRegistry.get_artifact_ids(self.id)
            for artifact_id in artifact_ids:
                ArtifactRegistry.sync_artifact_async(artifact_id)

    def _format(self) -> str:
        ...

    def update(self, **kwargs) -> None:
        ...

    async def aupdate(self, **kwargs) -> None:
        ...

class Markdown(ArtifactComponent):
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

    async def aupdate(self, markdown: str) -> None:
        """
        Update the markdown content and automatically sync if registered with an artifact.
        
        Args:
            markdown: New markdown content
        """
        self.markdown = markdown
        await self._sync_if_registered_async()

    def _format(self) -> str:
        return self.markdown

class Link(ArtifactComponent):
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

    async def aupdate(self, link: str, link_text: Optional[str] = None) -> None:
        """
        Update the link content and automatically sync if registered with an artifact.
        
        Args:
            link: New link URL
            link_text: New link text (optional)
        """
        self.link = link
        if link_text is not None:
            self.link_text = link_text
        await self._sync_if_registered_async()

    def _format(self) -> str:
        return f"[{self.link_text}]({self.link})" if self.link_text else f"[{self.link}]({self.link})"

class Progress(ArtifactComponent):
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

    async def aupdate(self, progress: float) -> None:
        """
        Update the progress value and automatically sync if registered with an artifact.
        
        Args:
            progress: New progress value (0-100)
        """
        self.progress = progress
        await self._sync_if_registered_async()

    def _format(self) -> float:
        # Ensure progress is between 0 and 100
        min_progress = 0.0
        max_progress = 100.0
        if self.progress < min_progress or self.progress > max_progress:
            self.progress = max(min_progress, min(self.progress, max_progress))

        return self.progress

class Image(ArtifactComponent):
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

    async def aupdate(self, image_url: str) -> None:
        """
        Update the image URL and automatically sync if registered with an artifact.
        
        Args:
            image_url: New image URL
        """
        self.image_url = image_url
        await self._sync_if_registered_async()

    def _format(self) -> str:
        return f"![{self.image_url}]({self.image_url})"

class Table(ArtifactComponent):
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

    async def aupdate(self, table: Union[dict[str, list[Any]], list[dict[str, Any]], list[list[Any]]]) -> None:
        """
        Update the table data and automatically sync if registered with an artifact.
        
        Args:
            table: New table data
        """
        self.table = table
        await self._sync_if_registered_async()

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