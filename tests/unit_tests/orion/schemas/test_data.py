from unittest.mock import MagicMock

import pytest
from typing_extensions import Literal

from prefect.orion.schemas.data import (
    DataDocument,
    FileSystemDataDocument,
    OrionDataDocument,
)


class TestDataDocument:
    def test_create_does_not_allow_unknown_encoding(self):
        with pytest.raises(ValueError, match="Unknown document encoding"):
            DataDocument.create(encoding="foo", data="test")

    def test_create_requires_dispatch_subclass_to_implement_encode(self):
        class TestDataDocument(DataDocument):
            encoding: Literal["foo"] = "foo"

        with pytest.raises(NotImplementedError):
            DataDocument.create(encoding="foo", data="test")

    def test_create_encodes_data_using_dispatcher(self):
        class TestDataDocument(DataDocument):
            encoding: Literal["foo"] = "foo"

            @staticmethod
            def encode(data):
                return data.encode()

        result = DataDocument.create(encoding="foo", data="test")
        assert result.encoding == "foo"
        assert result.blob == b"test"

    @pytest.mark.parametrize("cast", [True, False])
    def test_create_returns_class_or_subclass_depending_on_cast(self, cast):
        class TestDataDocument(DataDocument):
            encoding: Literal["foo"] = "foo"

            @staticmethod
            def encode(data):
                return data.encode()

        result = DataDocument.create(encoding="foo", data="test", cast=cast)
        assert isinstance(result, TestDataDocument if cast else DataDocument)

    @pytest.mark.parametrize(
        "encoding,expected",
        [
            ("orion", OrionDataDocument),
            ("file", FileSystemDataDocument),
            ("s3", FileSystemDataDocument),
        ],
    )
    def test_supports_known_server_encodings(self, encoding, expected, monkeypatch):
        # Mock encoding because the passed data will be invalid
        mock = MagicMock(return_value=b"data")
        monkeypatch.setattr(expected, "encode", mock)

        result = DataDocument.create(encoding=encoding, data="data", cast=True)
        assert isinstance(result, expected)
        assert result.encoding == encoding
        assert result.blob == b"data"


class UnicodeDataDocument(DataDocument[str]):
    encoding: Literal["utf-8"] = "utf-8"

    @staticmethod
    def encode(data):
        return data.encode()

    @staticmethod
    def decode(blob):
        return blob.decode()


class TestDataDocumentSubclass:
    def test_create_from_subclass(self):
        doc = UnicodeDataDocument.create("test")
        assert doc.blob == b"test"

    def test_datadoc_read_from_subclass(self):
        doc = UnicodeDataDocument.create("test")
        assert doc.read() == "test"

    def test_datadoc_caches_on_creation(self):
        doc = UnicodeDataDocument.create("test")
        assert doc._data == "test"

    def test_datadoc_cache_is_not_persisted(self):
        doc = UnicodeDataDocument.create("test")
        assert "_data" not in doc.dict()


@pytest.mark.parametrize("encodings", ["foo", ("foo", "bar")])
def test_datadoc_supported_encodings(encodings):
    class TestDataDocument(DataDocument):
        encoding: Literal[encodings]

    if isinstance(encodings, str):
        expected = tuple([encodings])
    else:
        expected = encodings

    assert TestDataDocument.supported_encodings() == expected


class TestFileSystemDataDocument:
    def test_create_writes_to_local_fs(self, tmpdir):
        path = str(tmpdir.join("test"))
        FileSystemDataDocument.create((path, b"data"), encoding="file")

        with open(tmpdir.join("test"), "rb") as fp:
            assert fp.read() == b"data"

    def test_reads_from_local_fs(self, tmpdir):
        path = str(tmpdir.join("test"))
        with open(path, "wb") as fp:
            fp.write(b"data")

        doc = FileSystemDataDocument(encoding="file", blob=path.encode())
        docpath, data = doc.read()
        assert data == b"data"
        assert docpath == path

    def test_requires_bytes(self):
        with pytest.raises(TypeError):
            # Raises in fsspec -- might be worth an explicit type check earlier
            FileSystemDataDocument.create(("test", "data"), encoding="file")


class TestOrionDataDocument:
    def test_create_and_read(self):
        fs_doc = FileSystemDataDocument(encoding="file", blob=b"file://this/is/my/path")
        orion_doc = OrionDataDocument.create(
            data=fs_doc,
        )

        assert orion_doc.blob == fs_doc.json().encode()
        assert orion_doc.read() == fs_doc
