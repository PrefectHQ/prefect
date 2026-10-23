import json
import logging
from copy import deepcopy
from typing import Any, Dict

import httpx
from anyio import Path
from cachetools import TTLCache
from fastapi import HTTPException, Request, status

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
async def read_view_content(view: str, request: Request) -> Dict[str, Any]:
    """Reads the content of a view from the prefect-collection-registry."""
    # Built at server startup; absent when the app runs without its lifespan
    local_worker_metadata = getattr(request.app.state, "local_worker_metadata", None)
    try:
        return await get_collection_view(
            view, local_worker_metadata=local_worker_metadata
        )
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


def _build_local_worker_metadata() -> dict[str, dict[str, dict[str, Any]]]:
    """Builds metadata for the worker types installed alongside the server.

    Building it imports every installed integration and renders each worker's
    default job template. Installed packages do not change while the server
    runs, so the server builds it once at startup, before it serves requests,
    and keeps it on the API app's state. It is merged into the registry's view
    on each request rather than cached with it, since the view cache is shared
    by every app in the process. A failure is logged, and the views then list
    only the workers the registry knows about.
    """
    try:
        return get_locally_installed_worker_metadata()
    except Exception:
        logger.warning(
            "Unable to read worker metadata from the local worker registry",
            exc_info=True,
        )
        return {}


def _merge_local_worker_metadata(
    data: dict[str, Any], local_metadata: dict[str, dict[str, dict[str, Any]]]
) -> None:
    """Adds worker types installed alongside the server that the view is missing.

    The registry only knows about published collections, so a worker from an
    unreleased or private integration would never appear in the UI's work pool
    creation flow. Registry entries win where both are present: the published
    metadata is canonical for collections the registry tracks.
    """
    known_types: set[str] = set()
    for collection in data.values():
        if not isinstance(collection, dict):
            continue
        for worker_type, worker in collection.items():
            known_types.add(worker_type)
            if isinstance(worker, dict) and worker.get("type"):
                known_types.add(worker["type"])

    for collection_name, workers in local_metadata.items():
        # Copies, so that changes to a served view cannot reach the metadata
        # built at startup, which lives as long as the server
        missing = {
            worker_type: deepcopy(worker)
            for worker_type, worker in workers.items()
            if worker_type not in known_types
        }
        if not missing:
            continue
        collection = data.setdefault(collection_name, {})
        # Leave a malformed registry entry as it is rather than fail the view
        if isinstance(collection, dict):
            collection.update(missing)


def _post_process_view(view: str, data: dict[str, Any]) -> dict[str, Any]:
    """Applies view-specific adjustments before a registry view is cached."""
    if view == "aggregate-worker-metadata":
        data.get("prefect", {}).pop("prefect-agent", None)
    return data


def _with_local_worker_metadata(
    view: str,
    data: dict[str, Any],
    local_worker_metadata: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Returns the view with the locally installed workers merged in.

    The merge goes into a copy, leaving the cached registry view as it was.
    """
    if view != "aggregate-worker-metadata" or not local_worker_metadata:
        return data
    merged = {
        name: dict(collection) if isinstance(collection, dict) else collection
        for name, collection in data.items()
    }
    _merge_local_worker_metadata(merged, local_worker_metadata)
    return merged


async def get_collection_view(
    view: str,
    local_worker_metadata: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return _with_local_worker_metadata(
        view, await _get_registry_view(view), local_worker_metadata or {}
    )


async def _get_registry_view(view: str) -> dict[str, Any]:
    """Returns a view from the registry, or from the copy bundled with Prefect
    when the registry cannot be reached, caching it either way."""
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
