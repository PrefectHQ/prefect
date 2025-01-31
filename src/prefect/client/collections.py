from typing import Any, Dict, Optional

from typing_extensions import Protocol

from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import ServerType, get_client


class CollectionsMetadataClient(Protocol):
    async def read_worker_metadata(self) -> Dict[str, Any]: ...

    async def __aenter__(self) -> "CollectionsMetadataClient": ...

    async def __aexit__(self, *exc_info: Any) -> Any: ...


def get_collections_metadata_client(
    httpx_settings: Optional[Dict[str, Any]] = None,
) -> "CollectionsMetadataClient":
    """
    Creates a client that can be used to fetch metadata for
    Prefect collections.

    Will return a `CloudClient` if profile is set to connect
    to Prefect Cloud, otherwise will return an `OrchestrationClient`.
    """
    orchestration_client = get_client(httpx_settings=httpx_settings)
    if orchestration_client.server_type == ServerType.CLOUD:
        return get_cloud_client(httpx_settings=httpx_settings, infer_cloud_url=True)
    else:
        return orchestration_client
