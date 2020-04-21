# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid
from typing import List

import pendulum
import pytest
from asynctest import CoroutineMock
from prefect.engine.state import Running

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
        slots=1,
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
    async def test_delete_existing(self, resource_pool: models.ResourcePool):

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        deleted = await api.resource_pools.delete_resource_pool(resource_pool.id)
        assert deleted is True

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        assert pool_count == (new_pool_count + 1)

    async def test_delete_bad_id(self, resource_pool: models.ResourcePool):

        pool_count = await orm.ModelQuery(model=models.ResourcePool).count()
        deleted = await api.resource_pools.delete_resource_pool(uuid.uuid4().hex)
        assert deleted is False

        new_pool_count = await orm.ModelQuery(model=models.ResourcePool).count()

        assert pool_count == new_pool_count


class TestGetAvailableResources:
    async def test_raises_error_without_params(
        self, resource_pool: models.ResourcePool
    ):

        with pytest.raises(TypeError):
            available_resources = await api.resource_pools.get_available_resources()

    @pytest.mark.parametrize(
        "resources", [["bigquery"], ["spark"], ["bigquery", "spark"]]
    )
    async def test_contains_in(self, labeled_flow_id: str, resources: List[str]):
        """
        This test doesn't necessarily test our code, but it does test
        that our understanding of how Hasura handles filtering a JSONB
        field with the structure:
        {
            key: [value, value2, value,3]
        }
        """
        result = await api.flows._update_flow_setting(
            labeled_flow_id, "resources", resources
        )
        assert result is True
        res = await models.Flow.where(
            {"settings": {"_contains": {"resources": resources}}}
        ).count()
        assert res == 1

    async def test_bottoms_out_at_0(
        self,
        flow_id: str,
        flow_run_id: str,
        flow_run_id_2: str,
        resource_pool: models.ResourcePool,
    ):
        """
        This test makes sure that in the case of over-allocating
        resources, we return 0 slots available so we can't
        over-over-allocate the resource.
        """

        result = await api.flows._update_flow_setting(
            flow_id, "resources", [resource_pool.name]
        )
        assert result is True

        available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )

        assert available_resources == 0

        await asyncio.gather(
            api.states.set_flow_run_state(flow_run_id, Running()),
            api.states.set_flow_run_state(flow_run_id_2, Running()),
        )

        available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )

        assert available_resources == 0

    async def test_only_includes_running_states(
        self,
        flow_id: str,
        flow_run_id: str,
        flow_run_id_2: str,
        resource_pool: models.ResourcePool,
    ):
        """
        Tests to make sure that only running states count towards
        the pool's resource usage.
        """

        result = await api.flows._update_flow_setting(
            flow_id, "resources", [resource_pool.name]
        )

        # Setting the limit higher so we can actually observe the changes
        await models.ResourcePool.where(id=resource_pool.id).update(set={"slots": 10})

        available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )

        assert available_resources == 9

        # Now that the flow is running, it should take up a spot in the pool
        await asyncio.gather(api.states.set_flow_run_state(flow_run_id, Running()))

        new_available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )
        # We should have 1 less spot due to the new flow run
        assert available_resources == (new_available_resources + 1)

    async def test_only_includes_resource_runs(
        self,
        flow_id: str,
        labeled_flow_id: str,
        labeled_flow_run_id: str,
        resource_pool: models.ResourcePool,
    ):
        """
        Tests to make sure that only flows that are tagged as using
        the resource count towards the pool's capacity.
        """
        await api.flows._update_flow_setting(flow_id, "resources", [resource_pool.name])

        # Setting the limit higher so we can actually observe the changes
        await models.ResourcePool.where(id=resource_pool.id).update(set={"slots": 10})

        available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )

        assert available_resources == 10

        # Marking the flow that _doesn't_ use the pool as running
        await asyncio.gather(
            api.states.set_flow_run_state(labeled_flow_run_id, Running())
        )

        new_available_resources = await api.resource_pools.get_available_resources(
            resource_pool.id
        )
        # No resource pool slots should be taken because it isn't tagged w/ the resource
        assert available_resources == new_available_resources
