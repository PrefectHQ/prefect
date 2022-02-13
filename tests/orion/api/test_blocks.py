from prefect.orion import schemas
from prefect.orion.schemas.actions import BlockDataCreate, BlockDataUpdate


class TestBlockData:
    async def test_creating_blocks(self, session, client):
        data = BlockDataCreate(
            name="really-useful-data",
            blockref="really-nice-api",
            data=dict(),
        ).dict(json_compatible=True)

        response = await client.post("/blocks/", json=data)
        assert response.status_code == 200
        assert response.json()["id"]

    async def test_creating_and_reading_blocks_by_name(self, session, client):
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

        create_response = await client.post("/blocks/", json=data)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        read_response = await client.get("/blocks/name/the-planeteers")
        block = read_response.json()

        assert block["blockid"] == block_id
        assert block["blockref"] == "captain-planet"
        assert block["ma-ti and suchi"] == "heart"

    async def test_creating_and_reading_block_data_by_id(self, session, client):
        data = BlockDataCreate(
            name="power-rangers",
            blockref="megazord",
            data={
                "red": "jason",
                "pink": "kimberly",
                "yellow": "trini",
                "blue": "billy",
                "black": "zack",
            },
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=data)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        read_response = await client.get(f"/blocks/{block_id}")
        block = read_response.json()

        assert block["blockname"] == "power-rangers"
        assert block["blockref"] == "megazord"
        assert block["red"] == "jason"
        assert block.get("green") is None, "the green ranger isn't needed for megazord"

    async def test_deleting_blocks_that_exist(self, session, client):
        data = BlockDataCreate(
            name="dont-mind-me",
            blockref="sneaky-crime-syndicate",
            data={"secret-identity": "evil-crime-lord"},
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=data)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        is_there_crime = await client.get(f"/blocks/name/dont-mind-me")
        assert is_there_crime.status_code == 200

        delete_response = await client.delete(f"/blocks/name/dont-mind-me")
        assert delete_response

        is_there_crime_now = await client.get(f"/blocks/name/dont-mind-me")
        assert is_there_crime_now.status_code == 404

    async def test_creating_a_block_with_duplicate_name(self, session, client):
        first_twin = BlockDataCreate(
            name="an-identical-twin",
            blockref="im-an-independent-person",
            data={"hobbies": "sports"},
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=first_twin)
        assert create_response.status_code == 200

        second_twin = BlockDataCreate(
            name="an-identical-twin",
            blockref="im-just-like-my-sibling",
            data={"hobbies": "watching sports"},
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=second_twin)
        assert create_response.status_code == 400

    async def test_updating_a_block(self, session, client):
        a_sad_block = BlockDataCreate(
            name="the-white-wizard",
            blockref="disappointment",
            data=dict(palantir="we do not know who else may be watching"),
        ).dict(json_compatible=True)
        create_response = await client.post("/blocks/", json=a_sad_block)
        assert create_response.status_code == 200

        a_better_wizard = BlockDataUpdate(
            name="mithrandir",
        ).dict(json_compatible=True)

        patch_response = await client.patch(
            "/blocks/name/the-white-wizard",
            json=a_better_wizard,
        )
        assert patch_response.status_code == 200
