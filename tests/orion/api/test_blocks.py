from prefect.orion import schemas
from prefect.orion.schemas.actions import BlockCreate, BlockUpdate


class TestBlock:
    async def test_creating_blocks(self, session, client):
        raw_block = {
            "blockname": "really-useful-data",
            "blockref": "really-nice-api",
        }

        block_create = schemas.actions.BlockCreate.from_serialized_block(
            raw_block
        ).dict(json_compatible=True)

        response = await client.post("/blocks/", json=block_create)
        assert response.status_code == 200
        assert response.json()["id"]

    async def test_creating_and_reading_blocks_by_name(self, session, client):
        raw_block = {
            "blockname": "the-planeteers",
            "blockref": "captain-planet",
            "kwame": "earth",
            "wheeler": "fire",
            "linka": "wind",
            "gi": "water",
            "ma-ti and suchi": "heart",
        }

        block_create = schemas.actions.BlockCreate.from_serialized_block(
            raw_block
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=block_create)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        read_response = await client.get("/blocks/name/the-planeteers")
        block = read_response.json()

        assert block["blockid"] == block_id
        assert block["blockref"] == "captain-planet"
        assert block["ma-ti and suchi"] == "heart"

    async def test_creating_and_reading_block_data_by_id(self, session, client):
        raw_block = {
            "blockname": "power-rangers",
            "blockref": "megazord",
            "red": "jason",
            "pink": "kimberly",
            "yellow": "trini",
            "blue": "billy",
            "black": "zack",
        }

        block_create = schemas.actions.BlockCreate.from_serialized_block(
            raw_block
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=block_create)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        read_response = await client.get(f"/blocks/{block_id}")
        block = read_response.json()

        assert block["blockname"] == "power-rangers"
        assert block["blockref"] == "megazord"
        assert block["red"] == "jason"
        assert block.get("green") is None, "the green ranger isn't needed for megazord"

    async def test_deleting_blocks_that_exist(self, session, client):
        raw_block = {
            "blockname": "dont-mind-me",
            "blockref": "sneaky-crime-syndicate",
            "secret-identity": "evil-crime-lord",
        }

        block_create = schemas.actions.BlockCreate.from_serialized_block(
            raw_block
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=block_create)
        assert create_response.status_code == 200
        block_id = create_response.json()["id"]

        is_there_crime = await client.get(f"/blocks/name/dont-mind-me")
        assert is_there_crime.status_code == 200

        delete_response = await client.delete(f"/blocks/name/dont-mind-me")
        assert delete_response

        is_there_crime_now = await client.get(f"/blocks/name/dont-mind-me")
        assert is_there_crime_now.status_code == 404

    async def test_creating_a_block_with_duplicate_name(self, session, client):
        first_twin = {
            "blockname": "an-identical-twin",
            "blockref": "im-an-independent-person",
            "hobbies": "sports",
        }

        first_twin_create = schemas.actions.BlockCreate.from_serialized_block(
            first_twin
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=first_twin_create)
        assert create_response.status_code == 200

        second_twin = {
            "blockname": "an-identical-twin",
            "blockref": "im-just-like-my-sibling",
            "hobbies": "watching sports",
        }

        second_twin_create = schemas.actions.BlockCreate.from_serialized_block(
            second_twin
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=second_twin_create)
        assert create_response.status_code == 400

    async def test_updating_a_block(self, session, client):
        a_sad_block = {
            "blockname": "the-white-wizard",
            "blockref": "disappointment",
            "palantir": "we do not know who else may be watching",
        }

        sad_block_create = schemas.actions.BlockCreate.from_serialized_block(
            a_sad_block
        ).dict(json_compatible=True)

        create_response = await client.post("/blocks/", json=sad_block_create)
        assert create_response.status_code == 200

        a_better_wizard = BlockUpdate(
            name="mithrandir",
        ).dict(json_compatible=True)

        patch_response = await client.patch(
            "/blocks/name/the-white-wizard",
            json=a_better_wizard,
        )
        assert patch_response.status_code == 200
