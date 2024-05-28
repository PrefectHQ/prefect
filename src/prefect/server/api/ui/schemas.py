from typing import Any, Dict

from fastapi import Body, Depends, HTTPException, status

from prefect.logging import get_logger
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import APIRouter
from prefect.utilities.schema_tools.hydration import HydrationContext, hydrate
from prefect.utilities.schema_tools.validation import (
    CircularSchemaRefError,
    build_error_obj,
    is_valid_schema,
    preprocess_schema,
    validate,
)

router = APIRouter(prefix="/ui/schemas", tags=["UI", "Schemas"])

logger = get_logger("server.api.ui.schemas")


@router.post("/validate")
async def validate_obj(
    json_schema: Dict[str, Any] = Body(..., embed=True, alias="schema"),
    values: Dict[str, Any] = Body(..., embed=True),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    schema = preprocess_schema(json_schema)

    try:
        is_valid_schema(schema, preprocess=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    async with db.session_context() as session:
        ctx = await HydrationContext.build(
            session=session, render_jinja=False, render_workspace_variables=True
        )

    hydrated_values = hydrate(values, ctx)
    try:
        errors = validate(hydrated_values, schema, preprocess=False)
    except CircularSchemaRefError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid schema: Unable to validate schema with circular references.",
        )
    error_obj = build_error_obj(errors)

    return error_obj
