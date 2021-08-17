from datetime import datetime
from typing import Set
from enum import Enum

from prefect.orion.utilities.schemas import APIBaseModel


class DataScheme(Enum):
    S3 = "s3"
    FILE = "file"
    INLINE = "inline"  # The blob remains on the data document at all times


class DataLocation(APIBaseModel):
    name: str
    scheme: DataScheme
    base_path: str = ""
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
