"""
Routes for interacting with saved search objects.
"""

from typing import List
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.server import PrefectRouter
from prefect.types._datetime import now

router: PrefectRouter = PrefectRouter(prefix="/saved_searches", tags=["SavedSearches"])


@router.put("/")
async def create_saved_search(
    saved_search: schemas.actions.SavedSearchCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.SavedSearch:
    """Gracefully creates a new saved search from the provided schema.

    If a saved search with the same name already exists, the saved search's fields are
    replaced.
    """

    # hydrate the input model into a full model
    saved_search = schemas.core.SavedSearch(**saved_search.model_dump())

    right_now = now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.saved_searches.create_saved_search(
            session=session, saved_search=saved_search
        )

    if model.created >= right_now:
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id}")
async def read_saved_search(
    saved_search_id: UUID = Path(..., description="The saved search id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.SavedSearch:
    """
    Get a saved search by id.
    """
    async with db.session_context() as session:
        saved_search = await models.saved_searches.read_saved_search(
            session=session, saved_search_id=saved_search_id
        )
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found"
        )
    return saved_search


@router.post("/filter")
async def read_saved_searches(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.SavedSearch]:
    """
    Query for saved searches.
    """
    async with db.session_context() as session:
        return await models.saved_searches.read_saved_searches(
            session=session,
            offset=offset,
            limit=limit,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    saved_search_id: UUID = Path(..., description="The saved search id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Delete a saved search by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.saved_searches.delete_saved_search(
            session=session, saved_search_id=saved_search_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found"
        )
