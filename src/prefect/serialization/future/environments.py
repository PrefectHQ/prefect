import datetime
from pydantic import Field
from typing import Dict, List, Any
import prefect
from prefect.utilities.serialization_future import PolymorphicSerializable


class Environment(PolymorphicSerializable):
    class Config:
        extra = "allow"

    # for ALL environments
    labels: List[str] = Field(default_factory=list)

    # DaskKubernetes
    docker_secret: str = None
    private_registry: bool = None
    min_workers: int = None
    max_workers: int = None

    # Remote
    executor: str = None
    executor_kwargs: Dict[str, Any] = None

    # RemoteDaskEnvironment
    address: str = None

    @classmethod
    def from_environment(cls, obj: prefect.environments.Environment) -> "Environment":
        return super()._from_object(obj)

    def to_environment(self) -> prefect.environments.Environment:
        return self._to_object()


class Storage(PolymorphicSerializable):
    class Config:
        extra = "allow"

    # for ALL storage
    flows: Dict[str, str]
    secrets: List[str] = None
    prefect_version: str = None

    # Azure
    container: str = None
    blob_name: str = None

    # Docker
    registry_url: str = None
    image_name: str = None
    image_tag: str = None

    # Local
    directory: str = None

    # GCS / S3
    bucket: str = None
    key: str = None

    # GCS
    project: str = None

    # S3
    client_options: Dict[str, Any] = None

    @classmethod
    def from_storage(cls, obj: prefect.environments.storage.Storage) -> "Storage":
        return super()._from_object(obj)

    def to_storage(self) -> prefect.environments.storage.Storage:
        return self._to_object()
