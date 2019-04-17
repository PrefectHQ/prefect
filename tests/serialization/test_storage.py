import prefect
from prefect.environments import storage
from prefect.serialization.storage import BytesSchema, DockerSchema, BaseStorageSchema


def test_bytes_storage_serialize():
    storage = storage.Storage()
    serialized = BaseStorageSchema().dump(storage)

    assert serialized
    assert serialized["__version__"] == prefect.__version__


def test_bytes_storage_serialize():
    bstorage = storage.Bytes()
    serialized = BytesSchema().dump(bstorage)

    assert serialized
    assert serialized["__version__"] == prefect.__version__


def test_docker_empty_serialize():
    docker = storage.Docker()
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flow_file_path"] == "/root/.prefect/flow_env.prefect"
    assert not serialized["image_name"]
    assert not serialized["image_tag"]
    assert not serialized["registry_url"]


def test_docker_full_serialize():
    docker = storage.Docker(
        registry_url="url", image_name="name", image_tag="tag", flow_file_path="path"
    )
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flow_file_path"] == "path"
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
