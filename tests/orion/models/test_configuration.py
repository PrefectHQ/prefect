from prefect.orion import models, schemas


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
