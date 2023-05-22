import re
from typing import Any, Optional, Dict, Set

import httpx
from fastapi import status
from prefect.client.cloud import CloudUnauthorizedError

import prefect.context
from prefect.logging.loggers import get_logger
import prefect.settings
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_CLOUD_API_URL,
    PREFECT_API_URL,
    PREFECT_DEBUG_MODE,
)
from prefect.workers.base import BaseWorker


def get_collections_metadata_client(
    host: Optional[str] = None,
    api_key: Optional[str] = None,
    httpx_settings: Optional[Dict] = None,
    infer_cloud_url: bool = False,
) -> "CollectionsMetadataClient":
    """
    Creates a client that can be used to fetch metadata for
    Prefect collections.
    """
    if httpx_settings is not None:
        httpx_settings = httpx_settings.copy()

    if api_key or PREFECT_API_KEY.value():
        if infer_cloud_url is False:
            host = host or PREFECT_CLOUD_API_URL.value()
        else:
            configured_url = prefect.settings.PREFECT_API_URL.value()
            host = re.sub(r"accounts/.{36}/workspaces/.{36}\Z", "", configured_url)
    else:
        host = PREFECT_API_URL.value()

    return CollectionsMetadataClient(
        host=host,
        api_key=api_key or PREFECT_API_KEY.value(),
        httpx_settings=httpx_settings,
    )


class CollectionsMetadataClient:
    def __init__(
        self,
        host: str,
        api_key: Optional[str] = None,
        httpx_settings: Optional[Dict] = None,
    ) -> None:
        httpx_settings = httpx_settings or dict()
        httpx_settings.setdefault("headers", dict())
        if api_key:
            httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def read_worker_metadata(self) -> Dict[str, Any]:
        return await self._get("collections/views/aggregate-worker-metadata")

    async def get_available_work_pool_types(self) -> Set[str]:
        work_pool_types = BaseWorker.get_all_available_worker_types()

        try:
            worker_metadata = await self.read_worker_metadata()
            for collection in worker_metadata.values():
                for worker in collection.values():
                    work_pool_types.append(worker.get("type"))
        except Exception:
            if PREFECT_DEBUG_MODE:
                get_logger().warning(
                    "Unable to get worker metadata from the collections registry",
                    exc_info=True,
                )
            # Return only work pool types from the local type registry if
            # the request to the collections registry fails.
            pass

        return set([type for type in work_pool_types if type is not None])

    async def get_default_base_job_template_for_type(
        self,
        type: str,
    ) -> Optional[Dict[str, Any]]:
        # Attempt to get the default base job template for the worker type
        # from the local type registry first.
        worker_cls = BaseWorker.get_worker_class_from_type(type)
        if worker_cls is not None:
            return worker_cls.get_default_base_job_template()

        # If the worker type is not found in the local type registry, attempt to
        # get the default base job template from the collections registry.
        try:
            worker_metadata = await self.read_worker_metadata()

            for collection in worker_metadata.values():
                for worker in collection.values():
                    if worker.get("type") == type:
                        return worker.get("default_base_job_configuration")
        except Exception:
            if PREFECT_DEBUG_MODE:
                get_logger().warning(
                    f"Unable to get default base job template for {type!r} worker type",
                    exc_info=True,
                )
            return None

    async def _get(self, route, **kwargs):
        try:
            res = await self._client.get(route, **kwargs)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise CloudUnauthorizedError
            else:
                raise exc

        return res.json()

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The `CloudClient` must be entered with an async context. Use 'async "
            "with CloudClient(...)' not 'with CloudClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"
