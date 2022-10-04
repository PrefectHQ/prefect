from prefect.filesystems import LocalFileSystem
from prefect.results import (
    FileReference,
    NotSet,
    NullResult,
    ResultConfig,
    ResultFactory,
    SerializedResult,
)
from prefect.serializers import JSONSerializer


async def test_defaults():
    config = ResultConfig()
    factory = await ResultFactory.from_result_config(config)

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert isinstance(result.blob, FileReference)
    assert result.has_cached_object()
    assert await result.load() == "test"

    # Test retrieval from the file system
    result._cache = NotSet
    assert await result.load() == "test"


async def test_no_persistence_location():
    config = ResultConfig(filesystem=None)
    factory = await ResultFactory.from_result_config(config)

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert result.blob == factory.serializer.dumps("test")
    assert result.has_cached_object()
    assert await result.load() == "test"


async def test_nulls_are_not_persisted():
    config = ResultConfig()
    factory = await ResultFactory.from_result_config(config)

    result = await factory.create_result(None)
    assert isinstance(result, NullResult)
    assert await result.load() is None


async def test_user_provided_serializer_by_slug():
    config = ResultConfig(filesystem=None, serializer="json")
    assert config.serializer == "json"
    factory = await ResultFactory.from_result_config(config)
    assert isinstance(factory.serializer, JSONSerializer)

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert result.serializer == factory.serializer
    assert result.blob == factory.serializer.dumps("test")
    assert result.has_cached_object()
    assert await result.load() == "test"


async def test_user_provided_serializer_instance():
    serializer = JSONSerializer(jsonlib="orjson")
    config = ResultConfig(filesystem=None, serializer=serializer)
    assert config.serializer == serializer
    factory = await ResultFactory.from_result_config(config)
    assert factory.serializer == serializer

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert result.serializer == serializer
    assert result.blob == serializer.dumps("test")
    assert result.has_cached_object()
    assert await result.load() == "test"


async def test_user_provided_filesystem_by_id(tmpdir):
    block = LocalFileSystem(basepath=str(tmpdir))
    block_id = await block.save("foo")
    config = ResultConfig(filesystem=block_id)
    assert config.filesystem == block_id
    factory = await ResultFactory.from_result_config(config)
    assert factory.filesystem_block == block
    assert factory.filesystem_block_id == block_id

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert result.blob.filesystem_id == factory.filesystem_block_id
    assert result.has_cached_object()
    assert await result.load() == "test"

    # Test retrieval from the file system
    result._cache = NotSet
    assert await result.load() == "test"


async def test_user_provided_filesystem_instance(tmpdir):
    block = LocalFileSystem(basepath=str(tmpdir))
    config = ResultConfig(filesystem=block)
    assert config.filesystem == block
    factory = await ResultFactory.from_result_config(config)
    assert factory.filesystem_block == block
    assert factory.filesystem_block_id == block._block_document_id

    result = await factory.create_result("test")
    assert isinstance(result, SerializedResult)
    assert result.blob.filesystem_id == factory.filesystem_block_id
    assert result.has_cached_object()
    assert await result.load() == "test"

    # Test retrieval from the file system
    result._cache = NotSet
    assert await result.load() == "test"
