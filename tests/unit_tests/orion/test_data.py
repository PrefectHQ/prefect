from prefect.orion.data import write_datadoc_blob, read_datadoc_blob
from prefect.orion.schemas.data import DataDocument, DataLocation, DataScheme


class TestWriteDataDoc:
    async def test_write_with_inline_scheme_is_noop(self):
        assert (
            await write_datadoc_blob(
                DataDocument(path="foo", blob=b"foo"),
                DataLocation(scheme=DataScheme.INLINE, name="test"),
            )
            is False
        )

    async def test_write_with_file_schema_writes_to_local_filesystem(self, tmpdir):
        assert (
            await write_datadoc_blob(
                DataDocument(path=str(tmpdir.join("test")), blob=b"data"),
                DataLocation(scheme=DataScheme.FILE, name="test"),
            )
            is True
        )
        with open(tmpdir.join("test"), "rb") as fp:
            assert fp.read() == b"data"


class TestReadDataDoc:
    async def test_read_with_inline_scheme_returns_doc_blob(self):
        blob = await read_datadoc_blob(
            DataDocument(path="foo", blob=b"data"),
            DataLocation(scheme=DataScheme.INLINE, name="test"),
        )
        assert blob == b"data"

    async def test_read_with_file_schema_reads_to_local_filesystem(self, tmpdir):

        with open(tmpdir.join("test"), "wb") as fp:
            fp.write(b"data")

        blob = await read_datadoc_blob(
            DataDocument(path=str(tmpdir.join("test"))),
            DataLocation(scheme=DataScheme.FILE, name="test"),
        )
        assert blob == b"data"
