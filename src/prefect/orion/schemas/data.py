from datetime import datetime
from typing import Set, Literal

from prefect.orion.utilities.schemas import ORMBaseModel


class DataLocation(ORMBaseModel):
    name: str
    scheme: Literal["s3", "file", "db"] = "db"
    base_path: str = "/tmp"
    tags: Set[str] = None
    is_healthy: bool = False
    last_health_check: datetime = None
    credential_name: str = None


class DataDocument(ORMBaseModel):
    path: str = None
    format: str = None
    name: str = None
    tags: Set[str] = None
    blob: bytes = None
