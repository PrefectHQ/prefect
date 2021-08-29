from unittest.mock import MagicMock

import pytest
from typing_extensions import Literal

from prefect.orion.schemas.data import DataDocument
from prefect.orion.serializers import (
    _SERIALIZERS,
    FileSerializer,
    OrionSerializer,
    Serializer,
    register_serializer,
)


@pytest.fixture(autouse=True)
def reset_registered_serializers(monkeypatch):
    _copy = _SERIALIZERS.copy()
    monkeypatch.setattr("prefect.orion.serializers", _copy)
    yield


class TestDataDocument:
    def test_encode_does_not_allow_unknown_encoding(self):
        with pytest.raises(ValueError, match="Unregistered encoding 'foo'"):
            DataDocument.encode(encoding="foo", data="test")

    def test_encode_requires_serializer_to_implement_dumps(self):
        @register_serializer("foo")
        class BadSerializer(Serializer):
            pass

        with pytest.raises(NotImplementedError):
            DataDocument.encode(encoding="foo", data="test")

    def test_encode_serializes_data_using_dispatcher(self):
        @register_serializer("foo")
        class FooSerializer(DataDocument):
            @staticmethod
            def dumps(data):
                return (data + "foo").encode()

        result = DataDocument.encode(encoding="foo", data="test")
        assert result.encoding == "foo"
        assert result.blob == b"testfoo"

    def test_decode_requires_serializer_to_implement_loads(self):
        @register_serializer("foo")
        class BadSerializer(Serializer):
            pass

        datadoc = DataDocument(encoding="foo", blob=b"test")

        with pytest.raises(NotImplementedError):
            datadoc.decode()

    def test_encode_deserializes_data_using_dispatcher(self):
        @register_serializer("foo")
        class FooSerializer(DataDocument):
            @staticmethod
            def loads(blob):
                return blob.decode() + "foo"

        datadoc = DataDocument(encoding="foo", blob=b"test")
        assert datadoc.decode() == "testfoo"

    @pytest.mark.parametrize(
        "encoding,serializer",
        [
            ("orion", OrionSerializer),
            ("file", FileSerializer),
            ("s3", FileSerializer),
        ],
    )
    def test_supports_known_server_encodings(self, encoding, serializer, monkeypatch):
        # Mock dumps because the passed data will be invalid
        mock = MagicMock(return_value=b"data")
        monkeypatch.setattr(serializer, "dumps", mock)

        result = DataDocument.encode(encoding=encoding, data="data")
        assert result.encoding == encoding
        assert result.blob == b"data"
