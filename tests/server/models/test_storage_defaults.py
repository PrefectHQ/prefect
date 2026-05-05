from uuid import UUID

from prefect.server import models, schemas


async def test_write_read_and_clear_server_default_result_storage(session):
    block_document_id = UUID("7cc65eb7-a8e2-4e0a-96aa-9527130d412d")

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
