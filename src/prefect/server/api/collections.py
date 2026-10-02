import json
import logging
from typing import Any, Dict

import httpx
from anyio import Path
from cachetools import TTLCache
from fastapi import HTTPException, status

from prefect.logging import get_logger
from prefect.server.utilities.server import PrefectRouter
from prefect.workers.utilities import get_locally_installed_worker_metadata

logger: logging.Logger = get_logger(__name__)

router: PrefectRouter = PrefectRouter(prefix="/collections", tags=["Collections"])

GLOBAL_COLLECTIONS_VIEW_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(
    maxsize=200, ttl=60 * 10
)

REGISTRY_VIEWS = (
    "https://raw.githubusercontent.com/PrefectHQ/prefect-collection-registry/main/views"
)
KNOWN_VIEWS = {
    "aggregate-block-metadata": f"{REGISTRY_VIEWS}/aggregate-block-metadata.json",
    "aggregate-flow-metadata": f"{REGISTRY_VIEWS}/aggregate-flow-metadata.json",
    "aggregate-worker-metadata": f"{REGISTRY_VIEWS}/aggregate-worker-metadata.json",
    "demo-flows": f"{REGISTRY_VIEWS}/demo-flows.json",
}


@router.get("/views/{view}")
async def read_view_content(view: str) -> Dict[str, Any]:
    """Reads the content of a view from the prefect-collection-registry."""
    try:
        return await get_collection_view(view)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"View {view} not found in registry",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requested content missing for view {view}",
            )
        else:
            raise


def _merge_local_worker_metadata(data: dict[str, Any]) -> None:
    """Adds worker types installed alongside the server that the view is missing.

    The registry only knows about published collections, so a worker from an
    unreleased or private integration would never appear in the UI's work pool
    creation flow. Registry entries win where both are present: the published
    metadata is canonical for collections the registry tracks.
    """
    try:
        local_metadata = get_locally_installed_worker_metadata()
    except Exception:
        logger.warning(
            "Unable to read worker metadata from the local worker registry",
            exc_info=True,
        )
        return

    known_types: set[str] = set()
    for collection in data.values():
        if not isinstance(collection, dict):
            continue
        for worker_type, worker in collection.items():
            known_types.add(worker_type)
            if isinstance(worker, dict) and worker.get("type"):
                known_types.add(worker["type"])

    for collection_name, workers in local_metadata.items():
        for worker_type, worker in workers.items():
            if worker_type in known_types:
                continue
            data.setdefault(collection_name, {})[worker_type] = worker


def _post_process_view(view: str, data: dict[str, Any]) -> dict[str, Any]:
    """Applies view-specific adjustments before a view is cached and served."""
    if view == "aggregate-worker-metadata":
        data.get("prefect", {}).pop("prefect-agent", None)
        _merge_local_worker_metadata(data)
    return data


async def get_collection_view(view: str) -> dict[str, Any]:
    try:
        return GLOBAL_COLLECTIONS_VIEW_CACHE[view]
    except KeyError:
        pass

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(KNOWN_VIEWS[view])
            resp.raise_for_status()

            data = _post_process_view(view, resp.json())

            GLOBAL_COLLECTIONS_VIEW_CACHE[view] = data
            return data
    except Exception:
        if view not in KNOWN_VIEWS:
            raise
        local_file = Path(__file__).parent / Path(f"collections_data/views/{view}.json")
        if await local_file.exists():
            raw_data = await local_file.read_text()
            data = _post_process_view(view, json.loads(raw_data))
            GLOBAL_COLLECTIONS_VIEW_CACHE[view] = data
            return data
        else:
            raise
