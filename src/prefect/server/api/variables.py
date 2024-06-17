"""
Routes for interacting with variable objects
"""

from typing import List, Optional
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models
from prefect.server.api.dependencies import LimitBody
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import actions, core, filters, sorting
from prefect.server.utilities.server import PrefectRouter


async def get_variable_or_404(session: AsyncSession, variable_id: UUID):
    """Returns a variable or raises 404 HTTPException if it does not exist"""

    variable = await models.variables.read_variable(
        session=session, variable_id=variable_id
    )
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found.")

    return variable


async def get_variable_by_name_or_404(session: AsyncSession, name: str):
    """Returns a variable or raises 404 HTTPException if it does not exist"""

    variable = await models.variables.read_variable_by_name(session=session, name=name)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found.")

    return variable


router = PrefectRouter(
    prefix="/variables",
    tags=["Variables"],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_variable(
    variable: actions.VariableCreate,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> core.Variable:
    async with db.session_context(begin_transaction=True) as session:
        model = await models.variables.create_variable(
            session=session, variable=variable
        )

    return core.Variable.model_validate(model, from_attributes=True)


@router.get("/{id:uuid}")
async def read_variable(
    variable_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> core.Variable:
    async with db.session_context() as session:
        model = await get_variable_or_404(session=session, variable_id=variable_id)

    return core.Variable.model_validate(model, from_attributes=True)


@router.get("/name/{name:str}")
async def read_variable_by_name(
    name: str = Path(...),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> core.Variable:
    async with db.session_context() as session:
        model = await get_variable_by_name_or_404(session=session, name=name)

    return core.Variable.model_validate(model, from_attributes=True)


@router.post("/filter")
async def read_variables(
    limit: int = LimitBody(),
    offset: int = Body(0, ge=0),
    variables: Optional[filters.VariableFilter] = None,
    sort: sorting.VariableSort = Body(sorting.VariableSort.NAME_ASC),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[core.Variable]:
    async with db.session_context() as session:
        return await models.variables.read_variables(
            session=session,
            variable_filter=variables,
            sort=sort,
            offset=offset,
            limit=limit,
        )


@router.post("/count")
async def count_variables(
    variables: Optional[filters.VariableFilter] = Body(None, embed=True),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    async with db.session_context() as session:
        return await models.variables.count_variables(
            session=session,
            variable_filter=variables,
        )


@router.patch("/{id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def update_variable(
    variable: actions.VariableUpdate,
    variable_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        updated = await models.variables.update_variable(
            session=session,
            variable_id=variable_id,
            variable=variable,
        )
    if not updated:
        raise HTTPException(status_code=404, detail="Variable not found.")


@router.patch("/name/{name:str}", status_code=status.HTTP_204_NO_CONTENT)
async def update_variable_by_name(
    variable: actions.VariableUpdate,
    name: str = Path(..., alias="name"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        updated = await models.variables.update_variable_by_name(
            session=session,
            name=name,
            variable=variable,
        )
    if not updated:
        raise HTTPException(status_code=404, detail="Variable not found.")


@router.delete("/{id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    variable_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        deleted = await models.variables.delete_variable(
            session=session, variable_id=variable_id
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Variable not found.")


@router.delete("/name/{name:str}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable_by_name(
    name: str = Path(...),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        deleted = await models.variables.delete_variable_by_name(
            session=session, name=name
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Variable not found.")
