import datetime
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.models.concurrency_limits import (
    read_concurrency_limit,
    read_concurrency_limit_by_tag,
)
from prefect.orion.schemas.actions import ConcurrencyLimitCreate
import prefect


class TestConcurrencyLimits:
    async def test_creating_concurrency_limits(self, session, client):
        data = ConcurrencyLimitCreate(
            tag="dummytag",
            concurrency_limit=42,
        ).dict(json_compatible=True)

        response = await client.post("/concurrency_limits/", json=data)
        assert response.status_code == 200
        cl_id = response.json()["id"]

    async def test_upserting_concurrency_limits(self, session, client):
        insert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=42,
        ).dict(json_compatible=True)

        insert_response = await client.post("/concurrency_limits/", json=insert_data)
        assert insert_response.status_code == 200
        assert insert_response.json()["concurrency_limit"] == 42
        first_update = insert_response.json()["updated"]

        upsert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=4242,
        ).dict(json_compatible=True)

        upsert_response = await client.post("/concurrency_limits/", json=upsert_data)
        assert upsert_response.status_code == 200
        assert upsert_response.json()["concurrency_limit"] == 4242
        assert first_update < upsert_response.json()["updated"]

    async def test_reading_concurrency_limits_by_id(self, session, client):
        data = ConcurrencyLimitCreate(
            tag="dummytag",
            concurrency_limit=42,
        ).dict(json_compatible=True)

        create_response = await client.post("/concurrency_limits/", json=data)
        cl_id = create_response.json()["id"]

        read_response = await client.get(f"/concurrency_limits/{cl_id}")
        concurrency_limit = schemas.core.ConcurrencyLimit.parse_obj(
            read_response.json()
        )
        assert concurrency_limit.tag == "dummytag"
        assert concurrency_limit.concurrency_limit == 42
        assert concurrency_limit.active_slots == 0

    async def test_creating_and_reading_concurrency_limits_by_tag(
        self, session, client
    ):
        tag = "anothertag"
        data = ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=4242,
        ).dict(json_compatible=True)

        create_response = await client.post("/concurrency_limits/", json=data)
        cl_id = create_response.json()["id"]

        read_response = await client.get(f"/concurrency_limits/tag/{tag}")
        concurrency_limit = schemas.core.ConcurrencyLimit.parse_obj(
            read_response.json()
        )
        assert str(concurrency_limit.id) == cl_id
        assert concurrency_limit.concurrency_limit == 4242
        assert concurrency_limit.active_slots == 0
