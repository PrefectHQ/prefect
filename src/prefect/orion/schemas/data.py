from datetime import datetime
from typing import Set, Literal

from prefect.orion.utilities.schemas import APIBaseModel


class DataLocation(APIBaseModel):
    name: str
    scheme: Literal["s3", "file", "db"] = "db"
    base_path: str = "/tmp"
    tags: Set[str] = None
    is_healthy: bool = False
    last_health_check: datetime = None
    credential_name: str = None


class DataDocument(APIBaseModel):
    path: str = None
    serializer: str = None
    name: str = None
    tags: Set[str] = None
    blob: bytes = None
