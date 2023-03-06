from typing import Any, Dict

import httpx
from cachetools import TTLCache
from fastapi import HTTPException, status

from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/collections", tags=["Collections"])

GLOBAL_COLLECTIONS_VIEW_CACHE: TTLCache = TTLCache(maxsize=200, ttl=60 * 10)


@router.get("/views/{view}")
async def read_view_content(view: str) -> Dict[str, Any]:
    """Reads the content of a view from the prefect-collection-registry."""
    try:
        return await get_collection_view(view)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requested content missing for view {view}",
            )
        else:
            raise


async def get_collection_view(view: str):
    try:
        return GLOBAL_COLLECTIONS_VIEW_CACHE[view]
    except KeyError:
        repo_organization = "PrefectHQ"
        repo_name = "prefect-collection-registry"

        repo_url = (
            f"https://raw.githubusercontent.com/{repo_organization}/{repo_name}/main"
        )

        view_filename = f"{view}.json"

        async with httpx.AsyncClient() as client:
            resp = await client.get(repo_url + f"/views/{view_filename}")
            resp.raise_for_status()

            GLOBAL_COLLECTIONS_VIEW_CACHE[view] = resp.json()
            return resp.json()
