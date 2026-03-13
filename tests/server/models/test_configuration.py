from uuid import UUID

from prefect.server import models, schemas


async def test_write_and_read_new_configuration(session):
    new_config = schemas.core.Configuration(key="foo", value={"foo": "bar"})
    await models.configuration.write_configuration(
        session=session, configuration=new_config
    )

    # read the configuration
    read_config = await models.configuration.read_configuration(
        session=session, key="foo"
    )
    assert isinstance(read_config, schemas.core.Configuration)
    assert read_config.key == "foo"
    assert read_config.value == {"foo": "bar"}

    # read it again to ensure any caching behaves
    read_config2 = await models.configuration.read_configuration(
        # passing session=None ensures the session can't be used
        session=None,
        key="foo",
    )
    assert isinstance(read_config2, schemas.core.Configuration)
    assert read_config2.key == "foo"
    assert read_config2.value == {"foo": "bar"}


async def test_write_configuration_multiple_times(session):
    # write a config
    new_config = schemas.core.Configuration(key="foo", value={"foo": "bar"})
    await models.configuration.write_configuration(
        session=session, configuration=new_config
    )

    # write another config for the same key
    new_config2 = schemas.core.Configuration(key="foo", value={"bar": "bar"})
    await models.configuration.write_configuration(
        session=session, configuration=new_config2
    )

    # read the configuration
    read_config = await models.configuration.read_configuration(
        session=session, key="foo"
    )
    assert isinstance(read_config, schemas.core.Configuration)
    assert read_config.key == "foo"
    assert read_config.value == {"bar": "bar"}


async def test_write_read_and_clear_server_default_result_storage(session):
    block_document_id = UUID("7cc65eb7-a8e2-4e0a-96aa-9527130d412d")

    await models.configuration.write_server_default_result_storage(
        session=session,
        configuration=schemas.core.ServerDefaultResultStorage(
            default_result_storage_block_id=block_document_id
        ),
    )

    read_config = await models.configuration.read_server_default_result_storage(
        session=session
    )
    assert read_config.default_result_storage_block_id == block_document_id

    cleared = await models.configuration.clear_server_default_result_storage(
        session=session
    )
    assert cleared is True

    empty_config = await models.configuration.read_server_default_result_storage(
        session=session
    )
    assert empty_config.default_result_storage_block_id is None
