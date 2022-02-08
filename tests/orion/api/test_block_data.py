from prefect.orion import schemas
from prefect.orion.schemas.actions import BlockDataCreate


class TestBlockData:
    async def test_creating_block_data(self, session, client):
        data = BlockDataCreate(
            name="really-useful-data",
            blockref="really-nice-api",
            data=dict(),
        ).dict(json_compatible=True)

        response = await client.post("/block_data/", json=data)
        assert response.status_code == 200
        assert response.json()["id"]

    async def test_creating_and_reading_block_data_by_name(self, session, client):
        data = BlockDataCreate(
            name="the-planeteers",
            blockref="captain-planet",
            data={
                "kwame": "earth",
                "wheeler": "fire",
                "linka": "wind",
                "gi": "water",
                "ma-ti and suchi": "heart",
            },
        ).dict(json_compatible=True)

        create_response = await client.post("/block_data/", json=data)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        read_response = await client.get("/block_data/name/the-planeteers")
        block = read_response.json()

        assert block["blockid"] == block_id
        assert block["blockref"] == "captain-planet"
        assert block["ma-ti and suchi"] == "heart"
