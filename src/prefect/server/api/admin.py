"""
Routes for admin-level interactions with the Prefect REST API.
"""

from fastapi import Depends, HTTPException, status

import prefect
import prefect.settings
from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(prefix="/admin", tags=["Admin"])


@router.get("/settings")
async def read_settings() -> prefect.settings.Settings:
    """
    Get the current Prefect REST API settings.

    Secret setting values will be obfuscated.
    """
    return prefect.settings.get_current_settings()


@router.get("/version")
async def read_version() -> str:
    """Returns the Prefect version number"""
    return prefect.__version__


@router.get("/storage")
async def read_server_default_result_storage(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ServerDefaultResultStorage:
    """Get the configured server default result storage block."""
    async with db.session_context() as session:
        return await models.configuration.read_server_default_result_storage(
            session=session
        )


@router.put("/storage")
async def update_server_default_result_storage(
    configuration: schemas.core.ServerDefaultResultStorage,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ServerDefaultResultStorage:
    """Set the server default result storage block."""
    async with db.session_context(begin_transaction=True) as session:
        block_document_id = configuration.default_result_storage_block_id
        if block_document_id is not None:
            block_document = await models.block_documents.read_block_document_by_id(
                session=session,
                block_document_id=block_document_id,
            )
            if block_document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Block document {block_document_id!s} not found.",
                )
            if (
                block_document.block_schema is None
                or "write-path" not in block_document.block_schema.capabilities
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Block document {block_document_id!s} cannot be used for "
                        "result storage."
                    ),
                )

        await models.configuration.write_server_default_result_storage(
            session=session,
            configuration=configuration,
        )

    return configuration


@router.delete("/storage", status_code=status.HTTP_204_NO_CONTENT)
async def clear_server_default_result_storage(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Clear the configured server default result storage block."""
    async with db.session_context(begin_transaction=True) as session:
        await models.configuration.clear_server_default_result_storage(session=session)
