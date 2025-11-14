from typing import List
from uuid import uuid4

import pytest
from httpx import AsyncClient
from starlette import status

from prefect.server import schemas
from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse
from prefect.server.schemas.actions import ConcurrencyLimitCreate
from prefect.settings import PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS


class TestConcurrencyLimits:
    async def test_creating_concurrency_limits(self, session, client):
        data = ConcurrencyLimitCreate(
            tag="dummytag",
            concurrency_limit=42,
        ).model_dump(mode="json")

        response = await client.post("/concurrency_limits/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["id"]

    async def test_upserting_concurrency_limits(self, session, client):
        insert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=42,
        ).model_dump(mode="json")

        insert_response = await client.post("/concurrency_limits/", json=insert_data)
        assert insert_response.status_code == status.HTTP_201_CREATED  # First create
        assert insert_response.json()["concurrency_limit"] == 42
        first_update = insert_response.json()["updated"]

        upsert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=4242,
        ).model_dump(mode="json")

        upsert_response = await client.post("/concurrency_limits/", json=upsert_data)
        assert upsert_response.status_code == status.HTTP_200_OK  # Update existing
        assert upsert_response.json()["concurrency_limit"] == 4242
        assert first_update < upsert_response.json()["updated"]

    async def test_reading_concurrency_limits_by_id(self, session, client):
        data = ConcurrencyLimitCreate(
            tag="dummytag",
            concurrency_limit=42,
        ).model_dump(mode="json")

        create_response = await client.post("/concurrency_limits/", json=data)
        cl_id = create_response.json()["id"]

        read_response = await client.get(f"/concurrency_limits/{cl_id}")
        concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
            read_response.json()
        )
        assert concurrency_limit.tag == "dummytag"
        assert concurrency_limit.concurrency_limit == 42
        assert concurrency_limit.active_slots == []

    async def test_creating_and_reading_concurrency_limits_by_tag(
        self, session, client
    ):
        tag = "anothertag"
        data = ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=4242,
        ).model_dump(mode="json")

        create_response = await client.post("/concurrency_limits/", json=data)
        cl_id = create_response.json()["id"]

        read_response = await client.get(f"/concurrency_limits/tag/{tag}")
        concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
            read_response.json()
        )
        assert str(concurrency_limit.id) == cl_id
        assert concurrency_limit.concurrency_limit == 4242
        assert concurrency_limit.active_slots == []

    async def test_resetting_concurrency_limits_by_tag(self, session, client):
        tag = "that's some tag"
        data = ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=4242,
        ).model_dump(mode="json")

        create_response = await client.post("/concurrency_limits/", json=data)
        cl_id = create_response.json()["id"]

        override_response = await client.post(
            f"/concurrency_limits/tag/{tag}/reset",
            json=dict(slot_override=[str(uuid4()) for _ in range(50)]),
        )
        assert override_response.status_code == status.HTTP_200_OK

        pre_reset = await client.get(f"/concurrency_limits/{cl_id}")
        assert len(pre_reset.json()["active_slots"]) == 50

        reset_response = await client.post(f"/concurrency_limits/tag/{tag}/reset")
        assert reset_response.status_code == status.HTTP_200_OK

        post_reset = await client.get(f"/concurrency_limits/{cl_id}")
        assert len(post_reset.json()["active_slots"]) == 0


class TestAcquiringAndReleasing:
    @pytest.fixture
    async def tags_with_limits(
        self,
        client: AsyncClient,
    ) -> List[str]:
        tags = ["tag1", "tag2"]

        for tag in tags:
            await client.post(
                "/concurrency_limits/",
                json=ConcurrencyLimitCreate(
                    tag=tag,
                    concurrency_limit=2,
                ).model_dump(mode="json"),
            )

        return tags

    async def test_acquiring_and_releasing_limits(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = tags_with_limits + ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        for tag in tags_with_limits:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert concurrency_limit.active_slots == [task_run_id]

        response = await client.post(
            "/concurrency_limits/decrement",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        # confirm the slots have been released

        for tag in tags_with_limits:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert concurrency_limit.active_slots == []

    async def test_failing_to_acquire_one_slot(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = tags_with_limits + ["does-not-exist"]

        # Acquire the slots by two random other task runs
        for i in range(2):
            response = await client.post(
                "/concurrency_limits/increment",
                json={"names": tags_with_limits[:1], "task_run_id": str(uuid4())},
            )
            assert response.status_code == status.HTTP_200_OK

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_423_LOCKED
        assert "Retry-After" in response.headers
        assert (
            0.0
            <= float(response.headers["Retry-After"])
            <= PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS.value() * 2
        )
        assert (
            "Concurrency limit for the tag1 tag has been reached"
            in response.json()["detail"]
        )

        for tag in tags_with_limits:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert task_run_id not in concurrency_limit.active_slots

        response = await client.post(
            "/concurrency_limits/decrement",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        # confirm the slots have been released

        for tag in tags_with_limits:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert task_run_id not in concurrency_limit.active_slots

    @pytest.fixture
    async def tag_with_zero_concurrency(
        self,
        client: AsyncClient,
    ) -> str:
        await client.post(
            "/concurrency_limits/",
            json=ConcurrencyLimitCreate(
                tag="zero",
                concurrency_limit=0,
            ).model_dump(mode="json"),
        )

        return "zero"

    async def test_setting_tag_to_zero_concurrency(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
        tag_with_zero_concurrency: str,
    ):
        task_run_id = uuid4()
        tags = tags_with_limits + [tag_with_zero_concurrency] + ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_423_LOCKED
        assert "Retry-After" not in response.headers
        assert (
            'The concurrency limit on tag "zero" is 0 and will deadlock if the task '
            "tries to run again." in response.json()["detail"]
        )

        for tag in tags_with_limits + [tag_with_zero_concurrency]:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert concurrency_limit.active_slots == []

        response = await client.post(
            "/concurrency_limits/decrement",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        # confirm the slots have been released

        for tag in tags_with_limits + [tag_with_zero_concurrency]:
            read_response = await client.get(f"/concurrency_limits/tag/{tag}")
            concurrency_limit = schemas.core.ConcurrencyLimit.model_validate(
                read_response.json()
            )
            assert concurrency_limit.active_slots == []

    async def test_acquiring_returns_limits(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = tags_with_limits + ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        limits = [
            MinimalConcurrencyLimitResponse.model_validate(limit)
            for limit in response.json()
        ]
        assert len(limits) == 2  # ignores tags that don't exist

    async def test_releasing_returns_limits(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = tags_with_limits + ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        response = await client.post(
            "/concurrency_limits/decrement",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK

        limits = [
            MinimalConcurrencyLimitResponse.model_validate(limit)
            for limit in response.json()
        ]
        assert len(limits) == 2  # ignores tags that don't exist

    async def test_acquiring_returns_empty_list_if_no_limits(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/increment",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_releasing_returns_empty_list_if_no_limits(
        self,
        client: AsyncClient,
        tags_with_limits: List[str],
    ):
        task_run_id = uuid4()
        tags = ["does-not-exist"]

        response = await client.post(
            "/concurrency_limits/decrement",
            json={"names": tags, "task_run_id": str(task_run_id)},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestV1ToV2Adapter:
    """Test the V1 API adapter that routes to V2 system."""

    async def test_create_creates_v2_limit_only(self, session, client):
        """Creating via V1 API should only create V2 limit, no V1 record."""
        data = ConcurrencyLimitCreate(
            tag="v2-only-tag",
            concurrency_limit=5,
        ).model_dump(mode="json")

        response = await client.post("/concurrency_limits/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        # Verify V1 format response
        result = response.json()
        assert result["tag"] == "v2-only-tag"
        assert result["concurrency_limit"] == 5
        assert result["active_slots"] == []

        # Can read it back via V1 API
        read_response = await client.get("/concurrency_limits/tag/v2-only-tag")
        assert read_response.status_code == status.HTTP_200_OK
        assert read_response.json()["tag"] == "v2-only-tag"
        assert read_response.json()["concurrency_limit"] == 5

    async def test_create_update_status_codes(self, session, client):
        """Test that create returns 201 and update returns 200."""
        data = ConcurrencyLimitCreate(
            tag="status-test",
            concurrency_limit=3,
        ).model_dump(mode="json")

        # First create should return 201
        create_response = await client.post("/concurrency_limits/", json=data)
        assert create_response.status_code == status.HTTP_201_CREATED

        # Second post (update) should return 200
        data["concurrency_limit"] = 5
        update_response = await client.post("/concurrency_limits/", json=data)
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["concurrency_limit"] == 5

    async def test_active_slots_from_v2_leases(self, session, client):
        """Test that active_slots are derived from V2 lease holders."""

        # Create limit
        data = ConcurrencyLimitCreate(
            tag="lease-test",
            concurrency_limit=3,
        ).model_dump(mode="json")
        response = await client.post("/concurrency_limits/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        # Acquire slots via increment (creates leases)
        task_ids = [str(uuid4()) for _ in range(2)]
        for task_id in task_ids:
            inc_response = await client.post(
                "/concurrency_limits/increment",
                json={"names": ["lease-test"], "task_run_id": task_id},
            )
            assert inc_response.status_code == status.HTTP_200_OK

        # Read and verify active_slots
        read_response = await client.get("/concurrency_limits/tag/lease-test")
        assert read_response.status_code == status.HTTP_200_OK
        data = read_response.json()
        assert len(data["active_slots"]) == 2
        assert set(data["active_slots"]) == set(task_ids)

    async def test_filter_merges_v1_and_v2(self, session, client):
        """Test that filter endpoint merges V1 and V2 limits properly."""
        from prefect.server import models, schemas

        # Create a V2 limit via adapter
        v2_data = ConcurrencyLimitCreate(
            tag="v2-filter",
            concurrency_limit=10,
        ).model_dump(mode="json")
        await client.post("/concurrency_limits/", json=v2_data)

        # Create a legacy V1 limit directly (simulating pre-migration)
        async with session as s:
            await models.concurrency_limits.create_concurrency_limit(
                session=s,
                concurrency_limit=schemas.core.ConcurrencyLimit(
                    tag="v1-filter",
                    concurrency_limit=20,
                ),
            )
            await s.commit()

        # Filter should return both
        response = await client.post("/concurrency_limits/filter", json={"limit": 100})
        assert response.status_code == status.HTTP_200_OK
        limits = response.json()

        tags = {limit["tag"] for limit in limits}
        assert "v2-filter" in tags
        assert "v1-filter" in tags

        # V2 should be preferred if same tag
        v2_limits = [lim for lim in limits if lim["tag"] == "v2-filter"]
        assert len(v2_limits) == 1
        assert v2_limits[0]["concurrency_limit"] == 10

    async def test_reset_handles_v2_limits(self, session, client):
        """Test that reset properly handles V2 limits with leases."""
        # Create limit
        data = ConcurrencyLimitCreate(
            tag="reset-v2",
            concurrency_limit=3,
        ).model_dump(mode="json")
        await client.post("/concurrency_limits/", json=data)

        # Acquire some slots
        task_ids = [str(uuid4()) for _ in range(2)]
        for task_id in task_ids:
            await client.post(
                "/concurrency_limits/increment",
                json={"names": ["reset-v2"], "task_run_id": task_id},
            )

        # Reset with override
        new_task_ids = [str(uuid4()) for _ in range(3)]
        reset_response = await client.post(
            "/concurrency_limits/tag/reset-v2/reset",
            json={"slot_override": new_task_ids},
        )
        assert reset_response.status_code == status.HTTP_200_OK

        # Verify new active slots
        read_response = await client.get("/concurrency_limits/tag/reset-v2")
        data = read_response.json()
        assert set(data["active_slots"]) == set(new_task_ids)

    async def test_delete_cleans_up_v2_leases(self, session, client):
        """Test that delete properly cleans up V2 limits and leases."""
        # Create limit
        data = ConcurrencyLimitCreate(
            tag="delete-v2",
            concurrency_limit=2,
        ).model_dump(mode="json")
        create_response = await client.post("/concurrency_limits/", json=data)
        assert create_response.status_code == status.HTTP_201_CREATED

        # Acquire a slot
        task_id = str(uuid4())
        await client.post(
            "/concurrency_limits/increment",
            json={"names": ["delete-v2"], "task_run_id": task_id},
        )

        # Delete by tag
        delete_response = await client.delete("/concurrency_limits/tag/delete-v2")
        assert delete_response.status_code == status.HTTP_200_OK

        # Verify it's gone via V1 API
        read_response = await client.get("/concurrency_limits/tag/delete-v2")
        assert read_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_pagination_when_many_leases(self, session, client):
        """Test that operations handle pagination properly with many active leases."""
        # Create a limit with high capacity
        data = ConcurrencyLimitCreate(
            tag="pagination-test",
            concurrency_limit=200,
        ).model_dump(mode="json")
        response = await client.post("/concurrency_limits/", json=data)
        assert response.status_code == status.HTTP_201_CREATED

        # Acquire 150 slots (more than typical batch size of 100)
        task_ids = []
        for i in range(150):
            task_id = str(uuid4())
            task_ids.append(task_id)
            inc_response = await client.post(
                "/concurrency_limits/increment",
                json={"names": ["pagination-test"], "task_run_id": task_id},
            )
            assert inc_response.status_code == status.HTTP_200_OK

        # Read should show all 150 active slots
        read_response = await client.get("/concurrency_limits/tag/pagination-test")
        assert read_response.status_code == status.HTTP_200_OK
        data = read_response.json()
        assert len(data["active_slots"]) == 150

        # Reset should clear all 150 leases (tests pagination in reset)
        reset_response = await client.post(
            "/concurrency_limits/tag/pagination-test/reset",
            json={"slot_override": []},
        )
        assert reset_response.status_code == status.HTTP_200_OK

        # Verify all slots cleared
        read_response = await client.get("/concurrency_limits/tag/pagination-test")
        data = read_response.json()
        assert len(data["active_slots"]) == 0

        # Re-acquire some slots for delete test
        for i in range(120):
            await client.post(
                "/concurrency_limits/increment",
                json={"names": ["pagination-test"], "task_run_id": task_ids[i]},
            )

        # Delete should clean up all 120 leases (tests pagination in delete)
        delete_response = await client.delete("/concurrency_limits/tag/pagination-test")
        assert delete_response.status_code == status.HTTP_200_OK

        # Verify it's gone
        read_response = await client.get("/concurrency_limits/tag/pagination-test")
        assert read_response.status_code == status.HTTP_404_NOT_FOUND
