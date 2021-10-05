import pytest

from prefect.orion.schemas.data import DataDocument
from prefect.orion.serializers import FileSerializer, OrionSerializer


def serialize_deserialize(obj, serializer, **dump_kwargs):
    return serializer.loads(serializer.dumps(obj, **dump_kwargs))


class TestFileSerializer:
    def test_encode_writes_to_local_fs(self, tmp_path):
        path = str(tmp_path.joinpath("test"))
        FileSerializer.dumps(b"data", path=path)

        with open(tmp_path.joinpath("test"), "rb") as fp:
            assert fp.read() == b"data"

    def test_reads_from_local_fs(self, tmp_path):
        path = str(tmp_path.joinpath("test"))
        with open(path, "wb") as fp:
            fp.write(b"data")

        assert FileSerializer.loads(path.encode()) == b"data"

    def test_roundtrip_data_is_unchanged(self, tmp_path):
        tmp_path = str(tmp_path.joinpath("test"))
        assert serialize_deserialize(b"test", FileSerializer, path=tmp_path) == b"test"

    def test_requires_bytes(self, tmp_path):
        with pytest.raises(TypeError):
            # Raises in fsspec -- might be worth an explicit type check earlier
            tmp_path = str(tmp_path.joinpath("test"))
            FileSerializer.dumps("data", path=tmp_path)

    def test_requires_path(self):
        with pytest.raises(TypeError):
            # `path` kwarg not provided
            FileSerializer.dumps(b"data")


class TestOrionSerializer:
    def test_dumps_is_pydantic_compatible(self):
        datadoc = DataDocument(encoding="foo", blob=b"bar")
        assert OrionSerializer.dumps(datadoc) == datadoc.json().encode()

    def test_loads_is_pydantic_compatible(self):
        datadoc = DataDocument(encoding="foo", blob=b"bar")
        assert OrionSerializer.loads(datadoc.json().encode()) == datadoc

    def test_roundtrip_data_is_unchanged(self):
        datadoc = DataDocument(encoding="foo", blob=b"bar")
        assert serialize_deserialize(datadoc, OrionSerializer) == datadoc
