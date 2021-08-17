from uuid import uuid4

import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateDataDocument:
    async def test_create_datadoc(self, client, session):
        datadoc_data = {"blob": "hello"}
        response = await client.post("/data/", json=datadoc_data)
        assert response.status_code == 201
        assert response.json()["blob"] == "hello"
        assert response.json()["id"]

        datadoc = await models.data.read_data_document(
            session=session, datadoc_id=response.json()["id"]
        )
        assert datadoc.blob == b"hello"

    async def test_create_multiple_datadocs(self, client, session):
        response1 = await client.post("/data/", json={"blob": "hello"})
        response2 = await client.post("/data/", json={"blob": "hello"})
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["blob"] == "hello"
        assert response2.json()["blob"] == "hello"
        assert response1.json()["id"] != response2.json()["id"]

        result = await session.execute(
            sa.select(models.orm.DataDocument.id).filter_by(blob=b"hello")
        )
        ids = result.scalars().all()
        assert {response1.json()["id"], response2.json()["id"]} == {str(i) for i in ids}


class TestReadDataDocument:
    async def test_read_data_document(self, client, session):
        datadoc = await models.data.create_data_document(
            session, schemas.actions.DataDocumentCreate(blob="hello")
        )
        # make sure we we can read the data doc correctly
        response = await client.get(f"/data/{datadoc.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(datadoc.id)
        assert response.json()["blob"] == "hello"

    async def test_read_data_document_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/data/{uuid4()}")
        assert response.status_code == 404
