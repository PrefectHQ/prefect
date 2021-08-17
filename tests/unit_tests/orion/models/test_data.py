from uuid import uuid4

from prefect.orion import models, schemas


class TestCreateDataDocument:
    async def test_create_data_document(self, session):
        datadoc = await models.data.create_data_document(
            session=session,
            datadoc=schemas.actions.DataDocumentCreate(blob=b"hello"),
        )
        assert datadoc.blob == b"hello"
        assert datadoc.path == "/" + datadoc.id.hex

    async def test_create_multiple_datadocs(self, session):
        datadoc_1 = await models.data.create_data_document(
            session=session,
            datadoc=schemas.actions.DataDocumentCreate(blob=b"hello"),
        )

        datadoc_2 = await models.data.create_data_document(
            session=session,
            datadoc=schemas.actions.DataDocumentCreate(blob=b"hello"),
        )

        assert datadoc_1.id != datadoc_2.id


class TestReadDataDocument:
    async def test_read_data_document(self, flow, session):
        # create a flow run to read
        datadoc = await models.data.create_data_document(
            session=session,
            datadoc=schemas.actions.DataDocumentCreate(blob=b"hello"),
        )

        read_data_document = await models.data.read_data_document(
            session=session, datadoc_id=datadoc.id
        )
        assert datadoc == read_data_document

    async def test_read_data_document_returns_none_if_does_not_exist(self, session):
        result = await models.data.read_data_document(
            session=session, datadoc_id=uuid4()
        )
        assert result is None
