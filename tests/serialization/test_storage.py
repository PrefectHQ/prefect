import prefect
from prefect.environments import storage
from prefect.serialization.storage import (
    BaseStorageSchema,
    DockerSchema,
    MemorySchema,
    BytesSchema,
)


def test_docker_empty_serialize():
    docker = storage.Docker()
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert not serialized["image_name"]
    assert not serialized["image_tag"]
    assert not serialized["registry_url"]


def test_memory_serialize():
    s = storage.Memory()
    serialized = MemorySchema().dump(s)

    assert serialized == {"__version__": prefect.__version__}


def test_memory_roundtrip():
    s = storage.Memory()
    s.add_flow(prefect.Flow("test"))
    serialized = MemorySchema().dump(s)

    assert serialized == {"__version__": prefect.__version__}
    deserialized = MemorySchema().load(serialized)
    assert deserialized.flows == dict()


def test_docker_full_serialize():
    docker = storage.Docker(registry_url="url", image_name="name", image_tag="tag")
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == dict()


def test_docker_serialize_with_flows():
    docker = storage.Docker(registry_url="url", image_name="name", image_tag="tag")
    f = prefect.Flow("test")
    docker.add_flow(f)
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == {"test": "/root/.prefect/test.prefect"}

    deserialized = DockerSchema().load(serialized)
    assert f.name in deserialized


def test_bytes_empty_serialize():
    b = storage.Bytes()
    serialized = BytesSchema().dump(b)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flows"] == dict()


def test_bytes_roundtrip():
    s = storage.Bytes()
    s.add_flow(prefect.Flow("test"))
    serialized = BytesSchema().dump(s)
    deserialized = BytesSchema().load(serialized)

    assert "test" in deserialized
    runner = deserialized.get_runner("test")
    assert runner.run().is_successful()
