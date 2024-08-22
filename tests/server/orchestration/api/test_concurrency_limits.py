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
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"]

    async def test_upserting_concurrency_limits(self, session, client):
        insert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=42,
        ).model_dump(mode="json")

        insert_response = await client.post("/concurrency_limits/", json=insert_data)
        assert insert_response.status_code == status.HTTP_200_OK
        assert insert_response.json()["concurrency_limit"] == 42
        first_update = insert_response.json()["updated"]

        upsert_data = ConcurrencyLimitCreate(
            tag="upsert tag",
            concurrency_limit=4242,
        ).model_dump(mode="json")

        upsert_response = await client.post("/concurrency_limits/", json=upsert_data)
        assert upsert_response.status_code == status.HTTP_200_OK
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
