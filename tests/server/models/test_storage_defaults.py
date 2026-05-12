from uuid import uuid4

import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.database import orm_models
from prefect.server.models.storage_defaults import (
    SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
)


async def test_write_read_and_clear_server_default_result_storage(session):
    block_document_id = uuid4()

    await models.storage_defaults.write_server_default_result_storage(
        session=session,
        storage_default=schemas.core.ServerDefaultResultStorage(
            default_result_storage_block_id=block_document_id
        ),
    )

    read_config = await models.storage_defaults.read_server_default_result_storage(
        session=session
    )
    assert read_config.default_result_storage_block_id == block_document_id

    cleared = await models.storage_defaults.clear_server_default_result_storage(
        session=session
    )
    assert cleared is True

    empty_config = await models.storage_defaults.read_server_default_result_storage(
        session=session
    )
    assert empty_config.default_result_storage_block_id is None


async def test_read_server_default_result_storage_bypasses_configuration_cache(session):
    cached_block_document_id = uuid4()
    updated_block_document_id = uuid4()

    await models.storage_defaults.write_server_default_result_storage(
        session=session,
        storage_default=schemas.core.ServerDefaultResultStorage(
            default_result_storage_block_id=cached_block_document_id
        ),
    )

    # Populate the generic configuration cache, then update the row directly to
    # simulate another server process writing the setting.
    await models.configuration.read_configuration(
        session=session,
        key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
    )
    await session.execute(
        sa.update(orm_models.Configuration)
        .where(
            orm_models.Configuration.key
            == SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY
        )
        .values(
            value=schemas.core.ServerDefaultResultStorage(
                default_result_storage_block_id=updated_block_document_id
            ).model_dump(mode="json")
        )
    )
    await session.flush()

    read_config = await models.storage_defaults.read_server_default_result_storage(
        session=session
    )

    assert read_config.default_result_storage_block_id == updated_block_document_id
