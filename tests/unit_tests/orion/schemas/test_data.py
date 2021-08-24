from unittest.mock import MagicMock

import pytest
from typing_extensions import Literal

from prefect.orion.schemas.data import (
    DataDocument,
    FileSystemDataDocument,
    OrionDataDocument,
    create_datadoc,
)


class TestCreateDataDoc:
    def test_create_datadoc_does_not_allow_unknown_encoding(self):
        with pytest.raises(ValueError, match="Unknown document encoding"):
            create_datadoc(encoding="foo", data="test")

    def test_create_datadoc_requires_subclass_encode(self):
        class TestDataDocument(DataDocument):
            encoding: Literal["foo"] = "foo"

        with pytest.raises(NotImplementedError):
            create_datadoc(encoding="foo", data="test")

    def test_create_datadoc_creates_subclass(self):
        class TestDataDocument(DataDocument):
            encoding: Literal["foo"] = "foo"

            @staticmethod
            def encode(data):
                return data.encode()

        result = create_datadoc(encoding="foo", data="test")
        assert isinstance(result, TestDataDocument)
        assert result.blob == b"test"

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

        # Create
        result = create_datadoc(encoding=encoding, data="data")
        assert isinstance(result, expected)


class UnicodeDataDocument(DataDocument[str]):
    encoding: Literal["utf-8"] = "utf-8"

    @staticmethod
    def encode(data):
        return data.encode()

    @staticmethod
    def decode(blob):
        return blob.decode()


class TestDataDoc:
    def test_datadoc_create(self):
        doc = UnicodeDataDocument.create("test")
        assert doc.blob == b"test"

    def test_datadoc_read(self):
        doc = UnicodeDataDocument.create("test")
        assert doc.read() == "test"

    def test_datadoc_caches_on_creation(self):
        doc = UnicodeDataDocument.create("test")
        assert doc._data_cache == "test"

    def test_datadoc_cache_is_not_persisted(self):
        doc = UnicodeDataDocument.create("test")
        assert "_data_cache" not in doc.dict()


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
