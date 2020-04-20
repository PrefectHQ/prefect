# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid

import pendulum
import pytest
from asynctest import CoroutineMock

from prefect_server import api
from prefect_server.database import models, orm


@pytest.fixture(autouse=True)
async def delete_resource_pools():
    """
    Database fixture that deletes all data related
    to a `Flow`, so we need to handle our resource
    pool. We _could_ add this into that fixture,
    but if we're only creating the pool for this
    set of tests, this is more straightforward.
    """

    await models.ResourcePool.where().delete()


@pytest.fixture
async def resource_pool() -> models.ResourcePool:

    pool_id = await api.resource_pools.create_resource_pool(
        "test pool",
        description="A resource pool created from Prefect Server's test suite.",
        slots=3,
    )

    populated_pool = await models.ResourcePool.where(id=pool_id).first(
        {"id", "name", "description", "slots"}
    )
    return populated_pool


class TestCreateResourcePool:
    async def test_creates_resource_pool(self):

        resource_pool_name = uuid.uuid4().hex
        description = "A resource pool created from Prefect Server's test suite."
        slots = 5

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        pool_id = await api.resource_pools.create_resource_pool(
            resource_pool_name, slots=slots, description=description
        )

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        assert (pool_count + 1) == new_pool_count

        pool = await models.ResourcePool.where(where={"id": {"_eq": pool_id}}).first(
            {"id", "name", "description", "slots"}
        )
        assert pool is not None
        assert pool.id == pool_id
        assert pool.description == description
        assert pool.slots == slots
        assert pool.name == resource_pool_name

    @pytest.mark.parametrize("slots", [0, -5])
    async def test_raises_error_on_bad_slots(self, slots: int):

        resource_pool_name = "test pool"
        description = "A resource pool created from Prefect Server's test suite."

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        with pytest.raises(ValueError):
            pool_id = await api.resource_pools.create_resource_pool(
                resource_pool_name, slots=slots, description=description
            )

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        # Making sure no create happened
        assert pool_count == new_pool_count

    async def test_conflicting_pool_name_raises_error(self):

        resource_pool_name = uuid.uuid4().hex
        description = "A resource pool created from Prefect Server's test suite."
        slots = 5

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        pool_id = await api.resource_pools.create_resource_pool(
            resource_pool_name, slots=slots, description=description
        )

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        assert (pool_count + 1) == new_pool_count

        with pytest.raises(ValueError):
            pool_id = await api.resource_pools.create_resource_pool(
                resource_pool_name, slots=slots, description=description
            )

        newest_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        assert newest_pool_count == new_pool_count


class TestDeleteResourcePool:
    async def test_delete_existing(self, resource_pool):

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        deleted = await api.resource_pools.delete_resource_pool(resource_pool.id)
        assert deleted is True

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        assert pool_count == (new_pool_count + 1)

    async def test_delete_bad_id(self, resource_pool):

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        deleted = await api.resource_pools.delete_resource_pool(uuid.uuid4().hex)
        assert deleted is False

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        assert pool_count == new_pool_count
