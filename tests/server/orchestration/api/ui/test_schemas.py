from httpx import AsyncClient


class TestUISchemasValidate:
    async def test_empty_schema_and_values(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/ui/schemas/validate",
            json={"schema": {}, "values": {}},
        )
        assert res.status_code == 200

    async def test_invalid_schema(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/ui/schemas/validate",
            json={
                "schema": {
                    "title": "Parameters",
                    "type": "NOT A REAL OBJECT RAWR",
                    "properties": {
                        "param": {"title": "param", "position": 0, "type": "integer"}
                    },
                    "required": ["param"],
                },
                "values": {"param": 1},
            },
        )
        assert res.status_code == 422, res.text
        res = res.json()
        assert (
            res["detail"]
            == "Invalid schema: 'NOT A REAL OBJECT RAWR' is not valid under any of the given schemas"
        )

    async def test_validation_passed(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/ui/schemas/validate",
            json={
                "schema": {
                    "title": "Parameters",
                    "type": "object",
                    "properties": {
                        "param": {"title": "param", "position": 0, "type": "integer"}
                    },
                    "required": ["param"],
                },
                "values": {"param": 1},
            },
        )
        assert res.status_code == 200, res.text
        res = res.json()
        assert "errors" in res and len(res["errors"]) == 0
        assert "valid" in res and res["valid"] is True

    async def test_validation_failed(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/ui/schemas/validate",
            json={
                "schema": {
                    "title": "Parameters",
                    "type": "object",
                    "properties": {
                        "param": {"title": "param", "position": 0, "type": "integer"}
                    },
                    "required": ["param"],
                },
                "values": {"param": "not an int"},
            },
        )
        assert res.status_code == 200, res.text
        res = res.json()
        assert res["errors"] == [
            {
                "property": "param",
                "errors": ["'not an int' is not of type 'integer'"],
            }
        ]
        assert "valid" in res and res["valid"] is False

    async def test_circular_schema_reference(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/ui/schemas/validate",
            json={
                "schema": {
                    "title": "Parameters",
                    "type": "object",
                    "properties": {
                        "param": {
                            "title": "param",
                            "position": 0,
                            "allOf": [{"$ref": "#/definitions/City"}],
                        }
                    },
                    "required": ["param"],
                    "definitions": {
                        "City": {
                            "title": "City",
                            "properties": {
                                "population": {
                                    "title": "Population",
                                    "type": "integer",
                                },
                                "name": {"title": "Name", "type": "string"},
                            },
                            "required": ["population", "name"],
                            # City definition references itself here
                            "allOf": [{"$ref": "#/definitions/City"}],
                        }
                    },
                },
                "values": {"param": "maybe a city, but we'll never know"},
            },
        )
        assert res.status_code == 422, res.text
        res = res.json()
        assert (
            res["detail"]
            == "Invalid schema: Unable to validate schema with circular references."
        )
