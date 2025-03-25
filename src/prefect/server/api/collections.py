import json
from typing import Any, Dict

import httpx
from anyio import Path
from cachetools import TTLCache
from fastapi import HTTPException, status

from prefect.server.utilities.server import PrefectRouter

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


async def get_collection_view(view: str) -> dict[str, Any]:
    try:
        return GLOBAL_COLLECTIONS_VIEW_CACHE[view]
    except KeyError:
        pass

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(KNOWN_VIEWS[view])
            resp.raise_for_status()

            data = resp.json()
            if view == "aggregate-worker-metadata":
                data.get("prefect", {}).pop("prefect-agent", None)

            GLOBAL_COLLECTIONS_VIEW_CACHE[view] = data
            return data
    except Exception:
        if view not in KNOWN_VIEWS:
            raise
        local_file = Path(__file__).parent / Path(f"collections_data/views/{view}.json")
        if await local_file.exists():
            raw_data = await local_file.read_text()
            data = json.loads(raw_data)
            GLOBAL_COLLECTIONS_VIEW_CACHE[view] = data
            return data
        else:
            raise
