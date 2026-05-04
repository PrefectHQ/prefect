from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database import orm_models
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models import block_documents, configuration

SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY = "server-default-result-storage"


async def validate_server_default_result_storage_block(
    session: AsyncSession,
    block_document_id: UUID,
) -> None:
    block_document = await block_documents.read_block_document_by_id(
        session=session,
        block_document_id=block_document_id,
    )
    if block_document is None:
        raise ObjectNotFoundError(f"Block document {block_document_id!s} not found.")

    block_schema = block_document.block_schema
    if block_schema is None or "write-path" not in block_schema.capabilities:
        raise ValueError(
            f"Block document {block_document_id!s} cannot be used for result storage."
        )


async def write_server_default_result_storage(
    session: AsyncSession,
    storage_default: schemas.core.ServerDefaultResultStorage,
) -> orm_models.Configuration:
    return await configuration.write_configuration(
        session=session,
        configuration=schemas.core.Configuration(
            key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
            value=storage_default.model_dump(mode="json"),
        ),
    )


async def read_server_default_result_storage(
    session: AsyncSession,
) -> schemas.core.ServerDefaultResultStorage:
    configured_value = await configuration.read_configuration(
        session=session,
        key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
        use_cache=False,
    )
    if configured_value is None:
        return schemas.core.ServerDefaultResultStorage()

    return schemas.core.ServerDefaultResultStorage.model_validate(
        configured_value.value
    )


async def clear_server_default_result_storage(session: AsyncSession) -> bool:
    return await configuration.delete_configuration(
        session=session,
        key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
    )
