import uuid
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import prefect
import prefect.server
from prefect._internal.compatibility.starlette import status
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool, WorkQueue
from prefect.server import models, schemas
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.core import WorkPoolStorageConfiguration
from prefect.server.schemas.statuses import DeploymentStatus, WorkQueueStatus
from prefect.utilities.pydantic import parse_obj_as

RESERVED_POOL_NAMES = [
    "Prefect",
    "Prefect Pool",
    "PrefectPool",
    "Prefect-Pool",
    "prefect",
    "prefect pool",
    "prefectpool",
    "prefect-pool",
]


@pytest.fixture(autouse=True)
def patch_events_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prefect.server.models.work_queues.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.models.workers.PrefectServerEventsClient",
        AssertingEventsClient,
    )


@pytest.fixture
async def invalid_work_pool(session):
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate.model_construct(
            _fields_set=schemas.actions.WorkPoolCreate.model_fields_set,
            name="wp-1",
            type="invalid",
            description="I have an invalid base job template!",
            base_job_template={
                "job_configuration": {
                    "thing_one": "{{ expected_variable_1 }}",
                    "thing_two": "{{ expected_variable_2 }}",
                },
                "variables": {
                    "properties": {
                        "not_expected_variable_1": {},
                        "expected_variable_2": {},
                    },
                    "required": [],
                },
            },
        ),
    )
    await session.commit()
    return work_pool


def assert_status_events(resource_name: str, events: List[str]):
    found_events = [
        event for item in AssertingEventsClient.all for event in item.events
    ]
    assert len(events) == len(found_events)

    for i, event in enumerate(events):
        assert event == found_events[i].event
        assert found_events[i].resource.name == resource_name


class TestCreateWorkPool:
    async def test_create_work_pool(self, session, client):
        response = await client.post(
            "/work_pools/",
            json=dict(
                name="Pool 1",
                type="test",
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        result = parse_obj_as(WorkPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is False
        assert result.concurrency_limit is None
        assert result.base_job_template == {}

        model = await models.workers.read_work_pool(
            session=session, work_pool_id=result.id
        )
        assert model
        assert model.name == "Pool 1"
        assert model.storage_configuration == WorkPoolStorageConfiguration()

        assert_status_events("Pool 1", ["prefect.work-pool.not-ready"])

    async def test_create_work_pool_with_storage_configuration(self, client):
        bundle_upload_step = {
            "prefect_aws.experimental.bundles.upload": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        bundle_execution_step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        default_result_storage_block_id = uuid.uuid4()
        data = schemas.actions.WorkPoolCreate(
            name="olympic",
            type="kubernetes",
            storage_configuration=schemas.core.WorkPoolStorageConfiguration(
                bundle_upload_step=bundle_upload_step,
                bundle_execution_step=bundle_execution_step,
                default_result_storage_block_id=default_result_storage_block_id,
            ),
        ).model_dump(mode="json")
        response = await client.post(
            "/work_pools/",
            json=data,
        )
        assert response.status_code == 201
        assert response.json()["storage_configuration"] == {
            "bundle_upload_step": bundle_upload_step,
            "bundle_execution_step": bundle_execution_step,
            "default_result_storage_block_id": str(default_result_storage_block_id),
        }

    async def test_create_work_pool_with_invalid_storage_configuration_key(
        self,
        client,
    ):
        response = await client.post(
            "/work_pools/",
            json={"storage_configuration": {"invalid_key": "invalid_value"}},
        )
        assert response.status_code == 422

    async def test_create_work_pool_with_options(self, client):
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", type="test", is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        result = parse_obj_as(WorkPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_work_pool_with_template(self, client):
        base_job_template = {
            "job_configuration": {
                "command": "{{ command }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    }
                },
                "required": [],
            },
        }

        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", type="test", base_job_template=base_job_template),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        result = parse_obj_as(WorkPool, response.json())
        assert result.base_job_template == base_job_template

    async def test_create_duplicate_work_pool(self, client, work_pool):
        response = await client.post(
            "/work_pools/",
            json=dict(name=work_pool.name, type="PROCESS"),
        )
        assert response.status_code == status.HTTP_409_CONFLICT, response.text

    @pytest.mark.parametrize("name", ["", "hi/there", "hi%there"])
    async def test_create_work_pool_with_invalid_name(self, client, name):
        response = await client.post("/work_pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )

    @pytest.mark.parametrize("name", ["''", " ", "' ' "])
    async def test_create_work_pool_with_emptyish_name(self, client, name):
        response = await client.post("/work_pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert "name cannot be an empty string" in response.content.decode()

    @pytest.mark.parametrize("type", ["PROCESS", "K8S", "AGENT"])
    async def test_create_typed_work_pool(self, session, client, type):
        response = await client.post(
            "/work_pools/", json=dict(name="Pool 1", type=type)
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        result = parse_obj_as(WorkPool, response.json())
        assert result.type == type

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_create_reserved_pool_fails(self, session, client, name):
        response = await client.post("/work_pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
        assert "reserved for internal use" in response.json()["detail"]

    async def test_create_work_pool_template_validation_missing_keys(self, client):
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template={"foo": "bar", "x": ["y"]}),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The `base_job_template` must contain both a `job_configuration` key and a"
            " `variables` key." in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_work_pool_template_validation_missing_variables(self, client):
        missing_variable_template = {
            "job_configuration": {
                "command": "{{ other_variable }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The variables specified in the job configuration template must be "
            "present as properties in the variables schema. "
            "Your job configuration uses the following undeclared "
            "variable(s): other_variable."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_work_pool_template_validation_missing_nested_variables(
        self, client
    ):
        missing_variable_template = {
            "job_configuration": {
                "config": {
                    "command": "{{ missing_variable }}",
                }
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The variables specified in the job configuration template must be "
            "present as properties in the variables schema. "
            "Your job configuration uses the following undeclared "
            "variable(s): missing_variable."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_work_pool_template_validation_missing_block_document(
        self,
        client,
    ):
        missing_block_doc_ref_template = {
            "job_configuration": {
                "block": "{{ block_string }}",
            },
            "variables": {
                "properties": {
                    "block_string": {
                        "type": "string",
                        "title": "Block String",
                        "default": {"$ref": {"block_document_id": "non-existing"}},
                    },
                },
                "required": ["block_string"],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_block_doc_ref_template),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert "Block not found" in response.json()["detail"]

    async def test_create_work_pool_template_validation_rejects_block_document_reference_incorrect_type(
        self,
        client,
        block_document,
    ):
        missing_block_doc_ref_template = {
            "job_configuration": {
                "block": "{{ block_string }}",
            },
            "variables": {
                "properties": {
                    "block_string": {
                        "type": "string",
                        "title": "Block String",
                        "default": {
                            "$ref": {"block_document_id": str(block_document.id)}
                        },
                    },
                },
                "required": ["block_string"],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_block_doc_ref_template),
        )
        assert (
            "Failure reason: {'foo': 'bar'} is not of type 'string'"
            in response.json()["detail"]
        )
        assert response.status_code == 422, response.text

    async def test_create_work_pool_template_validation_accepts_valid_block_document_reference(
        self,
        client,
        block_document,
    ):
        missing_block_doc_ref_template = {
            "job_configuration": {
                "block": "{{ block_object }}",
            },
            "variables": {
                "properties": {
                    "block_object": {
                        "type": "object",
                        "title": "Block Object",
                        "default": {
                            "$ref": {"block_document_id": str(block_document.id)}
                        },
                    },
                },
                "required": ["block_object"],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_block_doc_ref_template),
        )
        assert response.status_code == 201, response.text

    async def test_create_work_pool_with_3_3_7_client_version_does_not_include_default_result_storage_block_id(
        self,
        client: AsyncClient,
    ):
        response = await client.post(
            "/work_pools/",
            headers={"User-Agent": "prefect/3.3.7 (API 0.8.4)"},
            json=schemas.actions.WorkPoolCreate(
                name="test",
                type="kubernetes",
            ).model_dump(mode="json"),
        )
        assert response.status_code == 201
        assert response.json()["storage_configuration"] == {
            "bundle_upload_step": None,
            "bundle_execution_step": None,
        }


class TestDeleteWorkPool:
    async def test_delete_work_pool(self, client, work_pool, session):
        work_pool_id = work_pool.id
        response = await client.delete(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
        assert not await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool_id
        )

    async def test_nonexistent_work_pool(self, client):
        response = await client.delete("/work_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_delete_reserved_pool_fails(self, session, client, name):
        assert await models.workers.create_work_pool(
            session=session, work_pool=WorkPoolCreate(name=name)
        )
        await session.commit()

        response = await client.delete(f"/work_pools/{name}")
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
        assert "reserved for internal use" in response.json()["detail"]


class TestUpdateWorkPool:
    async def test_update_work_pool(self, client, session, work_pool):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

        assert_status_events(work_pool.name, ["prefect.work-pool.paused"])

    async def test_update_work_pool_storage_configuration(self, client, work_pool):
        bundle_upload_step = {
            "prefect_aws.experimental.bundles.upload": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        bundle_execution_step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        default_result_storage_block_id = uuid.uuid4()
        response = await client.get(f"/work_pools/{work_pool.name}")
        assert response.status_code == 200
        assert response.json()["storage_configuration"] == {
            "bundle_upload_step": None,
            "bundle_execution_step": None,
            "default_result_storage_block_id": None,
        }

        new_data = schemas.actions.WorkPoolUpdate(
            storage_configuration=schemas.core.WorkPoolStorageConfiguration(
                bundle_upload_step=bundle_upload_step,
                bundle_execution_step=bundle_execution_step,
                default_result_storage_block_id=default_result_storage_block_id,
            ),
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=new_data,
        )
        assert response.status_code == 204
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.json()["storage_configuration"] == {
            "bundle_upload_step": bundle_upload_step,
            "bundle_execution_step": bundle_execution_step,
            "default_result_storage_block_id": str(default_result_storage_block_id),
        }

    async def test_update_work_pool_storage_configuration_with_invalid_key(
        self,
        client,
        work_pool,
    ):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json={"storage_configuration": {"invalid_key": "invalid_value"}},
        )
        assert response.status_code == 422
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.json()["storage_configuration"] == {
            "bundle_upload_step": None,
            "bundle_execution_step": None,
            "default_result_storage_block_id": None,
        }

    async def test_clear_work_pool_storage_configuration(
        self,
        client,
    ):
        bundle_upload_step = {
            "prefect_aws.experimental.bundles.upload": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        bundle_execution_step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        default_result_storage_block_id = uuid.uuid4()
        create_response = await client.post(
            "/work_pools/",
            json={
                "name": "olympic",
                "type": "kubernetes",
                "storage_configuration": {
                    "bundle_upload_step": bundle_upload_step,
                    "bundle_execution_step": bundle_execution_step,
                    "default_result_storage_block_id": str(
                        default_result_storage_block_id
                    ),
                },
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["storage_configuration"] == {
            "bundle_upload_step": bundle_upload_step,
            "bundle_execution_step": bundle_execution_step,
            "default_result_storage_block_id": str(default_result_storage_block_id),
        }
        response = await client.patch(
            "/work_pools/olympic",
            json={"storage_configuration": {}},
        )
        assert response.status_code == 204
        work_pool_response = await client.get("/work_pools/olympic")
        assert work_pool_response.json()["storage_configuration"] == {
            "bundle_upload_step": None,
            "bundle_execution_step": None,
            "default_result_storage_block_id": None,
        }

    async def test_work_pool_storage_configuration_not_cleared_on_unrelated_update(
        self, client
    ):
        bundle_upload_step = {
            "prefect_aws.experimental.bundles.upload": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        bundle_execution_step = {
            "prefect_aws.experimental.bundles.execute": {
                "requires": "prefect-aws",
                "bucket": "MY_BUCKET_NAME",
                "aws_credentials_block_name": "MY_CREDS_BLOCK_NAME",
            },
        }
        default_result_storage_block_id = uuid.uuid4()
        await client.post(
            "/work_pools/",
            json={
                "name": "olympic",
                "type": "kubernetes",
                "storage_configuration": {
                    "bundle_upload_step": bundle_upload_step,
                    "bundle_execution_step": bundle_execution_step,
                    "default_result_storage_block_id": str(
                        default_result_storage_block_id
                    ),
                },
            },
        )
        response = await client.patch(
            "/work_pools/olympic",
            json={"description": "literally the newest"},
        )
        assert response.status_code == 204
        work_pool_response = await client.get("/work_pools/olympic")
        assert work_pool_response.json()["storage_configuration"] == {
            "bundle_upload_step": bundle_upload_step,
            "bundle_execution_step": bundle_execution_step,
            "default_result_storage_block_id": str(default_result_storage_block_id),
        }

    async def test_update_work_pool_with_no_workers(self, client, work_pool):
        assert work_pool.is_paused is False
        assert work_pool.status == schemas.statuses.WorkPoolStatus.NOT_READY.value

        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=schemas.actions.WorkPoolUpdate(is_paused=True).model_dump(
                mode="json", exclude_unset=True
            ),
        )

        assert response.status_code == 204, response.text

        response = await client.get(f"/work_pools/{work_pool.name}")

        assert response.json()["is_paused"] is True
        assert response.json()["status"] == schemas.statuses.WorkPoolStatus.PAUSED.value

        # Unpause the work pool
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=schemas.actions.WorkPoolUpdate(is_paused=False).model_dump(
                mode="json", exclude_unset=True
            ),
        )
        assert response.status_code == 204, response.text

        response = await client.get(f"/work_pools/{work_pool.name}")

        assert response.json()["is_paused"] is False
        assert (
            response.json()["status"] == schemas.statuses.WorkPoolStatus.NOT_READY.value
        )

        assert_status_events(
            work_pool.name, ["prefect.work-pool.paused", "prefect.work-pool.not-ready"]
        )

    async def test_unpause_work_pool_with_online_workers(self, client, work_pool):
        # Heartbeat a worker to make the work pool ready
        heartbeat_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.status_code == status.HTTP_200_OK
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.READY.value
        )

        # Pause the work pool
        pause_response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=schemas.actions.WorkPoolUpdate(is_paused=True).model_dump(
                mode="json", exclude_unset=True
            ),
        )
        assert pause_response.status_code == 204

        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")

        assert work_pool_response.json()["is_paused"] is True
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.PAUSED.value
        )

        # Unpause the work pool
        unpause_response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=schemas.actions.WorkPoolUpdate(is_paused=False).model_dump(
                mode="json", exclude_unset=True
            ),
        )
        assert unpause_response.status_code == 204

        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")

        assert work_pool_response.json()["is_paused"] is False
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.READY.value
        )

        assert_status_events(
            work_pool.name,
            [
                "prefect.work-pool.ready",
                "prefect.work-pool.paused",
                "prefect.work-pool.ready",
            ],
        )

    async def test_update_work_pool_zero_concurrency(
        self, client, session, work_pool, db
    ):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(concurrency_limit=0),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        async with db.session_context() as session:
            result = await models.workers.read_work_pool(
                session=session, work_pool_id=work_pool.id
            )
        assert result.concurrency_limit == 0

    async def test_update_work_pool_invalid_concurrency(
        self, client, session, work_pool
    ):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(concurrency_limit=-5),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.concurrency_limit is None

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_update_reserved_pool(self, session, client, name):
        assert await models.workers.create_work_pool(
            session=session, work_pool=WorkPoolCreate(name=name)
        )
        await session.commit()

        # fails if we try to update the description
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(description=name, is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
        assert "reserved for internal use" in response.json()["detail"]

        # succeeds if just pause and concurrency
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    async def test_update_work_pool_template(self, session, client):
        name = "Pool 1"

        base_job_template = {
            "job_configuration": {
                "command": "{{ command }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        pool = await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name, base_job_template=base_job_template),
        )
        await session.commit()

        base_job_template["variables"]["properties"]["command"]["default"] = ["woof!"]
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(base_job_template=base_job_template),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=pool.id
        )
        assert result.base_job_template["variables"]["properties"]["command"][
            "default"
        ] == ["woof!"]

    async def test_update_work_pool_template_validation_missing_keys(
        self, client, session
    ):
        name = "Pool 1"

        await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name),
        )
        await session.commit()

        session.expunge_all()

        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(name=name, base_job_template={"foo": "bar", "x": ["y"]}),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The `base_job_template` must contain both a `job_configuration` key and a"
            " `variables` key." in response.json()["exception_detail"][0]["msg"]
        )

    async def test_update_work_pool_template_validation_missing_variables(
        self, client, session
    ):
        name = "Pool 1"
        missing_variable_template = {
            "job_configuration": {
                "command": "{{ other_variable }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name),
        )
        await session.commit()

        session.expunge_all()

        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(name=name, base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The variables specified in the job configuration template must be "
            "present as properties in the variables schema. "
            "Your job configuration uses the following undeclared "
            "variable(s): other_variable."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_update_work_pool_template_validation_missing_nested_variables(
        self, client, session
    ):
        name = "Pool 1"
        missing_variable_template = {
            "job_configuration": {
                "config": {
                    "command": "{{ missing_variable }}",
                }
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }

        await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name),
        )
        await session.commit()

        session.expunge_all()

        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(name="Pool 1", base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert (
            "The variables specified in the job configuration template must be "
            "present as properties in the variables schema. "
            "Your job configuration uses the following undeclared "
            "variable(s): missing_variable."
            in response.json()["exception_detail"][0]["msg"]
        )


class TestReadWorkPool:
    async def test_read_work_pool(self, client, work_pool):
        response = await client.get(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_200_OK, response.text
        result = parse_obj_as(WorkPool, response.json())
        assert result.name == work_pool.name
        assert result.id == work_pool.id
        assert result.status == schemas.statuses.WorkPoolStatus.NOT_READY.value

    async def test_read_invalid_config(self, client):
        response = await client.get("/work_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_read_work_pool_that_fails_validation(
        self,
        client,
        invalid_work_pool,
    ):
        response = await client.get(f"/work_pools/{invalid_work_pool.name}")
        assert response.status_code == 200, response.text
        assert response.json()["id"] == str(invalid_work_pool.id)
        assert response.json()["name"] == "wp-1"

    async def test_read_work_pool_with_3_3_7_client_version_does_not_include_default_result_storage_block_id(
        self, client: AsyncClient, work_pool: WorkPool
    ):
        response = await client.get(
            f"/work_pools/{work_pool.name}",
            headers={"User-Agent": "prefect/3.3.7 (API 0.8.4)"},
        )
        assert response.status_code == 200
        assert response.json()["storage_configuration"] == {
            "bundle_upload_step": None,
            "bundle_execution_step": None,
        }


class TestReadWorkPools:
    @pytest.fixture(autouse=True)
    async def create_work_pools(self, client):
        for name in ["C", "B", "A"]:
            await client.post("/work_pools/", json=dict(name=name, type="test"))

    async def test_read_work_pools(self, client, session):
        response = await client.post("/work_pools/filter")
        assert response.status_code == status.HTTP_200_OK, response.text
        result = parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["A", "B", "C"]

    async def test_read_work_pools_with_limit(self, client, session):
        response = await client.post("/work_pools/filter", json=dict(limit=2))
        assert response.status_code == status.HTTP_200_OK, response.text
        result = parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["A", "B"]

    async def test_read_work_pools_with_offset(self, client, session):
        response = await client.post("/work_pools/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK, response.text
        result = parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["B", "C"]

    async def test_read_work_pool_with_work_pool_that_fails_validation(
        self,
        client,
        invalid_work_pool,
    ):
        response = await client.post("/work_pools/filter")
        assert response.status_code == 200, response.text
        assert len(response.json()) == 4

    async def test_read_work_pool_with_3_3_7_client_version_does_not_include_default_result_storage_block_id(
        self,
        client: AsyncClient,
    ):
        response = await client.post(
            "/work_pools/filter",
            headers={"User-Agent": "prefect/3.3.7 (API 0.8.4)"},
        )
        assert response.status_code == 200
        for work_pool in response.json():
            assert work_pool["storage_configuration"] == {
                "bundle_upload_step": None,
                "bundle_execution_step": None,
            }


class TestCountWorkPools:
    @pytest.fixture(autouse=True)
    async def create_work_pools(self, client):
        for name in ["C", "B", "A"]:
            await client.post("/work_pools/", json=dict(name=name, type="test"))

    async def test_count_work_pools(self, client):
        response = await client.post("/work_pools/count")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == 3

    async def test_count_work_pools_applies_filter(self, client):
        response = await client.post(
            "/work_pools/count", json={"work_pools": {"name": {"any_": ["A"]}}}
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == 1


class TestCreateWorkQueue:
    async def test_create_work_queue(self, client, work_pool):
        response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        result = parse_obj_as(WorkQueue, response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"
        assert result.work_pool_name == work_pool.name

    async def test_create_work_queue_with_priority(
        self,
        client,
        session,
        work_pool,
    ):
        data = dict(name="my-wpq", priority=99)
        response = await client.post(
            f"work_pools/{work_pool.name}/queues",
            json=data,
        )
        assert response.status_code == 201, response.text
        assert response.json()["priority"] == 99
        work_queue_id = response.json()["id"]

        work_queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert work_queue.priority == 99

    async def test_create_work_queue_with_no_priority_when_low_priority_set(
        self,
        client,
        work_pool,
    ):
        response = await client.post(
            f"work_pools/{work_pool.name}/queues", json=dict(name="wpq-1")
        )
        # priority 2 because the default queue exists
        assert response.json()["priority"] == 2

        response2 = await client.post(
            f"work_pools/{work_pool.name}/queues", json=dict(name="wpq-2")
        )
        assert response2.json()["priority"] == 3

    async def test_create_work_queue_with_no_priority_when_high_priority_set(
        self,
        client,
        session,
        work_pool,
    ):
        response = await client.post(
            f"work_pools/{work_pool.name}/queues", json=dict(name="wpq-1", priority=99)
        )
        assert response.json()["priority"] == 99
        work_queue_id = response.json()["id"]

        response2 = await client.post(
            f"work_pools/{work_pool.name}/queues", json=dict(name="wpq-2")
        )
        assert response2.json()["priority"] == 2

        work_queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert work_queue.priority == 99


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_pool):
        # Create work pool queue
        create_response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        read_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = parse_obj_as(WorkQueue, read_response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"
        assert result.work_pool_name == work_pool.name


class TestUpdateWorkQueue:
    @pytest.fixture
    async def paused_work_queue(self, session: AsyncSession):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-xyz", description="All about my work queue"
            ),
        )
        work_queue.status = WorkQueueStatus.PAUSED
        await session.commit()
        return work_queue

    @pytest.fixture
    async def ready_work_queue(self, session: AsyncSession):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-zzz", description="All about my work queue"
            ),
        )

        work_queue.status = WorkQueueStatus.READY
        await session.commit()
        return work_queue

    async def test_update_work_queue(self, client, work_pool):
        # Create work pool queue
        create_response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        create_result = parse_obj_as(WorkQueue, create_response.json())
        assert not create_result.is_paused

        # Update work pool queue
        update_response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/test-queue",
            json=dict(
                name="updated-test-queue",
                description="updated test queue",
                is_paused=True,
            ),
        )
        assert update_response.status_code == status.HTTP_204_NO_CONTENT

        # Read updated work pool queue
        read_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/updated-test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = parse_obj_as(WorkQueue, read_response.json())
        assert result.name == "updated-test-queue"
        assert result.description == "updated test queue"
        assert result.is_paused

    async def test_update_work_queue_to_paused(
        self,
        client,
        work_queue_1,
        work_pool,
    ):
        assert work_queue_1.is_paused is False
        assert work_queue_1.concurrency_limit is None
        assert work_queue_1.status == "NOT_READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=new_data,
        )

        assert response.status_code == 204, response.text

        response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3
        assert response.json()["status"] == "PAUSED"

        assert_status_events(work_queue_1.name, ["prefect.work-queue.paused"])

    async def test_update_work_queue_to_paused_sets_paused_status(
        self,
        client,
        work_queue_1,
        work_pool,
    ):
        assert work_queue_1.status == "NOT_READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=new_data,
        )

        assert response.status_code == 204, response.text

        response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3

        work_queue_response = await client.get(
            f"/work_queues/{work_queue_1.id}",
        )

        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "PAUSED"

        assert_status_events(work_queue_1.name, ["prefect.work-queue.paused"])

    async def test_update_work_queue_to_paused_when_already_paused_does_not_emit_event(
        self,
        client,
        paused_work_queue,
    ):
        assert paused_work_queue.status == "PAUSED"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True,
            concurrency_limit=3,  # type: ignore
        ).model_dump(mode="json", exclude_unset=True)
        work_queue_response = await client.patch(
            f"/work_queues/{paused_work_queue.id}",
            json=new_data,
        )

        assert work_queue_response.status_code == 204

        work_queue_response = await client.get(f"/work_queues/{paused_work_queue.id}")

        assert work_queue_response.json()["is_paused"] is True
        assert work_queue_response.json()["concurrency_limit"] == 3
        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "PAUSED"

        # ensure no events emitted for already paused work queue
        AssertingEventsClient.assert_emitted_event_count(0)

    async def test_update_work_queue_to_unpaused_when_already_unpaused_does_not_emit_event(
        self,
        client,
        ready_work_queue,
    ):
        assert ready_work_queue.status == "READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=False,
            concurrency_limit=3,  # type: ignore
        ).model_dump(mode="json", exclude_unset=True)
        work_queue_response = await client.patch(
            f"/work_queues/{ready_work_queue.id}",
            json=new_data,
        )

        assert work_queue_response.status_code == 204

        work_queue_response = await client.get(f"/work_queues/{ready_work_queue.id}")

        assert work_queue_response.json()["is_paused"] is False
        assert work_queue_response.json()["concurrency_limit"] == 3
        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "READY"

        # ensure no events emitted for already unpaused work queue
        AssertingEventsClient.assert_emitted_event_count(0)

    async def test_update_work_queue_to_unpaused_with_no_last_polled_sets_not_ready_status(
        self,
        client,
        work_queue_1,
        work_pool,
    ):
        # first, pause the work pool queue with no last_polled
        pause_data = schemas.actions.WorkQueueUpdate(is_paused=True).model_dump(  # type: ignore
            mode="json", exclude_unset=True
        )

        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=pause_data,
        )
        assert response.status_code == 204, response.text
        response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["is_paused"] is True
        assert paused_work_queue_response["last_polled"] is None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause the work pool queue with no last_polled
        unpause_data = schemas.actions.WorkQueueUpdate(  # type: ignore
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=unpause_data,
        )
        assert response.status_code == 204, response.text
        unpaused_data_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "NOT_READY"
        assert unpaused_data_response.json()["last_polled"] is None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.not-ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_unpaused_with_expired_last_polled_sets_not_ready_status(
        self,
        client,
        work_queue_1,
        work_pool,
    ):
        # first, pause the work pool queue with a expired last_polled
        pause_data = schemas.actions.WorkQueueUpdate(  # type: ignore
            last_polled=datetime.now(timezone.utc) - timedelta(minutes=2),
            is_paused=True,
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=pause_data,
        )
        assert response.status_code == 204, response.text
        response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["is_paused"] is True
        assert paused_work_queue_response["last_polled"] is not None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause the work pool queue with expired last_polled
        unpause_data = schemas.actions.WorkQueueUpdate(  # type: ignore
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=unpause_data,
        )
        assert response.status_code == 204, response.text
        unpaused_data_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "NOT_READY"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.not-ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_unpaused_with_recent_last_polled_sets_ready_status(
        self,
        client,
        work_queue_1,
        work_pool,
    ):
        # first, pause the work pool queue with a recent last_polled
        pause_data = schemas.actions.WorkQueueUpdate(  # type: ignore
            last_polled=datetime.now(timezone.utc), is_paused=True
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=pause_data,
        )
        assert response.status_code == 204, response.text
        response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["last_polled"] is not None
        assert paused_work_queue_response["is_paused"] is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause a recently polled work pool queue
        unpause_data = schemas.actions.WorkQueueUpdate(  # type: ignore
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
            json=unpause_data,
        )
        assert response.status_code == 204, response.text
        unpaused_data_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/{work_queue_1.name}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "READY"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue_1.id}",
                "prefect.resource.name": work_queue_1.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.name": work_pool.name,
                    "prefect.work-pool.type": work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )


class TestWorkPoolStatus:
    async def test_work_pool_status_with_online_worker(self, client, work_pool):
        """Work pools with an online work should have a status of READY."""
        await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )

        response = await client.get(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_200_OK, response.text

        result = parse_obj_as(WorkPool, response.json())
        assert result.status == schemas.statuses.WorkPoolStatus.READY

    async def test_work_pool_status_with_offline_worker(
        self, client, work_pool, session, db
    ):
        """Work pools with only offline workers should have a status of NOT_READY."""
        now = datetime.now(timezone.utc)

        insert_stmt = db.queries.insert(db.Worker).values(
            name="old-worker",
            work_pool_id=work_pool.id,
            last_heartbeat_time=now - timedelta(minutes=5),
        )

        await session.execute(insert_stmt)
        await session.commit()

        response = await client.get(f"/work_pools/{work_pool.name}")
        result = parse_obj_as(WorkPool, response.json())

        assert result.status == schemas.statuses.WorkPoolStatus.NOT_READY

    async def test_work_pool_status_with_no_workers(self, client, work_pool):
        """Work pools with no workers should have a status of NOT_READY."""
        response = await client.get(f"/work_pools/{work_pool.name}")
        result = parse_obj_as(WorkPool, response.json())

        assert result.status == schemas.statuses.WorkPoolStatus.NOT_READY

    async def test_work_pool_status_for_paused_work_pool(self, client, work_pool):
        """Work pools that are paused should have a status of PAUSED."""
        # Pause work pool
        await client.patch(f"/work_pools/{work_pool.name}", json=dict(is_paused=True))

        # Heartbeat worker
        await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )

        response = await client.get(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_200_OK, response.text

        result = parse_obj_as(WorkPool, response.json())
        assert result.is_paused
        assert result.status == schemas.statuses.WorkPoolStatus.PAUSED

    async def test_work_pool_status_for_prefect_agent_work_pool(
        self, client, prefect_agent_work_pool
    ):
        """Work pools that are Prefect Agent work pools should have `null` for status."""
        response = await client.get(f"/work_pools/{prefect_agent_work_pool.name}")
        assert response.status_code == status.HTTP_200_OK, response.text

        result = parse_obj_as(WorkPool, response.json())
        assert result.status is None


class TestWorkerProcess:
    async def test_heartbeat_worker(self, client, work_pool):
        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 0

        dt = datetime.now(timezone.utc)
        response = await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "test-worker"
        assert (
            datetime.fromisoformat(
                workers_response.json()[0]["last_heartbeat_time"].replace("Z", "+00:00")
            )
            > dt
        )
        assert workers_response.json()[0]["status"] == "ONLINE"

        assert_status_events(work_pool.name, ["prefect.work-pool.ready"])

    async def test_worker_heartbeat_updates_work_pool_status(self, client, work_pool):
        # Verify that the work pool is not ready
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.status_code == status.HTTP_200_OK
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.NOT_READY.value
        )

        # Heartbeat a worker
        heartbeat_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify that the work pool is ready
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.status_code == status.HTTP_200_OK
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.READY.value
        )

        assert_status_events(work_pool.name, ["prefect.work-pool.ready"])

    async def test_worker_heartbeat_does_not_updates_work_pool_status_if_paused(
        self, client, work_pool
    ):
        # Pause the work pool
        await client.patch(
            f"/work_pools/{work_pool.name}",
            json=schemas.actions.WorkPoolUpdate(is_paused=True).model_dump(
                mode="json", exclude_unset=True
            ),
        )

        # Verify that the work pool is paused
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.status_code == status.HTTP_200_OK
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.PAUSED.value
        )

        # Heartbeat a worker
        heartbeat_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert heartbeat_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify that the work pool is still paused
        work_pool_response = await client.get(f"/work_pools/{work_pool.name}")
        assert work_pool_response.status_code == status.HTTP_200_OK
        assert (
            work_pool_response.json()["status"]
            == schemas.statuses.WorkPoolStatus.PAUSED.value
        )

        assert_status_events(work_pool.name, ["prefect.work-pool.paused"])

    async def test_heartbeat_worker_requires_name(self, client, work_pool):
        response = await client.post(f"/work_pools/{work_pool.name}/workers/heartbeat")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            response.text
        )
        assert b'"missing","loc":["body","name"]' in response.content

    async def test_heartbeat_worker_upserts_for_same_name(self, client, work_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            await client.post(
                f"/work_pools/{work_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 2

    async def test_heartbeat_worker_limit(self, client, work_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            await client.post(
                f"/work_pools/{work_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
            json=dict(limit=1),
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "another-worker"

    async def test_heartbeat_accepts_heartbeat_interval(self, client, work_pool):
        await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker", heartbeat_interval_seconds=60),
        )

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
        )
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["heartbeat_interval_seconds"] == 60

    async def test_worker_with_old_heartbeat_has_offline_status(
        self, client, work_pool, session, db
    ):
        now = datetime.now(timezone.utc)

        insert_stmt = db.queries.insert(db.Worker).values(
            name="old-worker",
            work_pool_id=work_pool.id,
            last_heartbeat_time=now - timedelta(minutes=5),
        )

        await session.execute(insert_stmt)
        await session.commit()

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
        )
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["status"] == "OFFLINE"

    async def test_worker_status_accounts_for_heartbeat_interval(
        self, client, work_pool, session, db
    ):
        """
        Worker status should use the heartbeat interval to determine if a worker is
        offline.

        This test sets an abnormally small heartbeat interval and then checks that the
        worker is still considered offline than it would by default.
        """
        now = datetime.now(timezone.utc)

        insert_stmt = db.queries.insert(db.Worker).values(
            name="old-worker",
            work_pool_id=work_pool.id,
            last_heartbeat_time=now - timedelta(seconds=10),
            heartbeat_interval_seconds=1,
        )

        await session.execute(insert_stmt)
        await session.commit()

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
        )
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["status"] == "OFFLINE"


class TestReadWorkers:
    @pytest.fixture
    async def setup_workers(self, session, db, work_pool):
        # Create an ONLINE worker via heartbeat
        await models.workers.worker_heartbeat(
            session=session,
            work_pool_id=work_pool.id,
            worker_name="online-worker",
        )

        insert_stmt = db.queries.insert(db.Worker).values(
            name="offline-worker",
            work_pool_id=work_pool.id,
            status="OFFLINE",
        )
        await session.execute(insert_stmt)

        await session.commit()

    async def test_read_workers(self, client, work_pool):
        response = await client.post(f"/work_pools/{work_pool.name}/workers/filter")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.usefixtures("setup_workers")
    @pytest.mark.parametrize("worker_status", ["ONLINE", "OFFLINE"])
    async def test_read_workers_filter_by_status(
        self, client, work_pool, worker_status
    ):
        response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
            json=dict(workers=dict(status=dict(any_=[worker_status]))),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(data := response.json()) == 1, data
        assert data[0]["status"] == worker_status


class TestDeleteWorker:
    async def test_delete_worker(self, client, work_pool, session, db):
        work_pool_id = work_pool.id
        deleted_worker_name = "worker1"
        for i in range(2):
            insert_stmt = (db.queries.insert(db.Worker)).values(
                name=f"worker{i}",
                work_pool_id=work_pool_id,
                last_heartbeat_time=datetime.now(timezone.utc),
            )
            await session.execute(insert_stmt)
            await session.commit()

        response = await client.delete(
            f"/work_pools/{work_pool.name}/workers/{deleted_worker_name}"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
        remaining_workers = await models.workers.read_workers(
            session=session,
            work_pool_id=work_pool_id,
        )
        assert deleted_worker_name not in map(lambda x: x.name, remaining_workers)

    async def test_nonexistent_worker(self, client, session, db):
        worker_name = "worker1"
        wp = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="A"),
        )
        insert_stmt = (db.queries.insert(db.Worker)).values(
            name=worker_name,
            work_pool_id=wp.id,
            last_heartbeat_time=datetime.now(timezone.utc),
        )
        await session.execute(insert_stmt)
        await session.commit()

        response = await client.delete(f"/work_pools/{wp.name}/workers/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


class TestGetScheduledRuns:
    @pytest.fixture(autouse=True)
    async def setup(self, session, flow):
        """
        Creates:
        - Three different work pools ("A", "B", "C")
        - Three different queues in each pool ("AA", "AB", "AC", "BA", "BB", "BC", "CA", "CB", "CC")
        - One pending run, one running run, and 5 scheduled runs in each queue
        """

        # create three different work pools
        wp_a = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="A"),
        )
        wp_b = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="B"),
        )
        wp_c = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="C"),
        )

        # create three different work queues for each config
        wq_aa = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AA"),
        )
        wq_ab = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AB"),
        )
        wq_ac = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AC"),
        )
        wq_ba = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BA"),
        )
        wq_bb = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BB"),
        )
        wq_bc = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BC"),
        )
        wq_ca = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CA"),
        )
        wq_cb = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CB"),
        )
        wq_cc = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CC"),
        )

        # create flow runs
        for wq in [wq_aa, wq_ab, wq_ac, wq_ba, wq_bb, wq_bc, wq_ca, wq_cb, wq_cc]:
            # create a running run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.server.schemas.states.Running(),
                    work_queue_id=wq.id,
                ),
            )

            # create a pending run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.server.schemas.states.Pending(),
                    work_queue_id=wq.id,
                ),
            )

            # create 5 scheduled runs from two hours ago to three hours in the future
            # we insert them in reverse order to ensure that sorting is taking
            # place (and not just returning the database order)
            for i in range(3, -2, -1):
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        state=prefect.server.schemas.states.Scheduled(
                            scheduled_time=datetime.now(timezone.utc)
                            + timedelta(hours=i)
                        ),
                        work_queue_id=wq.id,
                    ),
                )
        await session.commit()

        return dict(
            work_pools=dict(wp_a=wp_a, wp_b=wp_b, wp_c=wp_c),
            work_queues=dict(
                wq_aa=wq_aa,
                wq_ab=wq_ab,
                wq_ac=wq_ac,
                wq_ba=wq_ba,
                wq_bb=wq_bb,
                wq_bc=wq_bc,
                wq_ca=wq_ca,
                wq_cb=wq_cb,
                wq_cc=wq_cc,
            ),
        )

    @pytest.fixture
    def work_pools(self, setup):
        return setup["work_pools"]

    @pytest.fixture
    def work_queues(self, setup):
        return setup["work_queues"]

    @pytest.fixture
    async def deployment(self, setup, session, flow):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                tags=["test"],
                flow_id=flow.id,
                work_queue_id=setup["work_queues"]["wq_aa"].id,
            ),
        )
        await session.commit()
        return deployment

    async def test_get_all_runs(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
        )
        assert response.status_code == status.HTTP_200_OK, response.text

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 15

        # runs are not sorted by time because they're sorted by queue priority
        assert data != sorted(data, key=lambda r: r.flow_run.next_scheduled_start_time)

    async def test_get_all_runs_limit(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(limit=7),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 7

    async def test_get_all_runs_wq_aa(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_aa"].name]),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 5

    async def test_get_all_runs_wq_aa_wq_ab(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                work_queue_names=[
                    work_queues["wq_aa"].name,
                    work_queues["wq_ab"].name,
                ]
            ),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 10

    async def test_get_all_runs_wq_ba_wrong_pool(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_ba"].name]),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_get_all_runs_scheduled_before(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_before=datetime.now(timezone.utc).isoformat()),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 6

    async def test_get_all_runs_scheduled_after(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_after=datetime.now(timezone.utc).isoformat()),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 9

    async def test_get_all_runs_scheduled_before_and_after(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                scheduled_before=str(datetime.now(timezone.utc) - timedelta(hours=1)),
                scheduled_after=str(datetime.now(timezone.utc)),
            ),
        )

        data = parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 0

    async def test_updates_last_polled_on_a_single_work_queue(
        self, client, work_queues, work_pools
    ):
        now = datetime.now(timezone.utc)
        poll_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_aa"].name]),
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queue_response = await client.get(
            f"/work_pools/{work_pools['wp_a'].name}/queues/{work_queues['wq_aa'].name}"
        )
        assert work_queue_response.status_code == status.HTTP_200_OK

        work_queue = parse_obj_as(WorkQueue, work_queue_response.json())
        work_queues_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = parse_obj_as(List[WorkQueue], work_queues_response.json())

        for work_queue in work_queues:
            if work_queue.name == "AA":
                assert work_queue.last_polled is not None
                assert work_queue.last_polled > now
            else:
                assert work_queue.last_polled is None

    async def test_updates_last_polled_on_a_multiple_work_queues(
        self, client, work_queues, work_pools
    ):
        now = datetime.now(timezone.utc)
        poll_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                work_queue_names=[
                    work_queues["wq_aa"].name,
                    work_queues["wq_ab"].name,
                ]
            ),
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queues_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = parse_obj_as(List[WorkQueue], work_queues_response.json())

        for work_queue in work_queues:
            if work_queue.name == "AA" or work_queue.name == "AB":
                assert work_queue.last_polled is not None
                assert work_queue.last_polled > now
            else:
                assert work_queue.last_polled is None

    async def test_updates_last_polled_on_a_full_work_pool(
        self, client, session, work_queues, work_pools
    ):
        work_pool = work_pools["wp_a"]
        work_queues["wq_aa"].status = WorkQueueStatus.NOT_READY
        work_queues["wq_ab"].status = WorkQueueStatus.PAUSED
        work_queues["wq_ac"].status = WorkQueueStatus.READY
        await session.commit()

        now = datetime.now(timezone.utc)
        poll_response = await client.post(
            f"/work_pools/{work_pool.name}/get_scheduled_flow_runs",
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queues_response = await client.post(
            f"/work_pools/{work_pool.name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = parse_obj_as(List[WorkQueue], work_queues_response.json())

        for work_queue in work_queues:
            assert work_queue.last_polled is not None, (
                "Work queue should have updated last_polled"
            )
            assert work_queue.last_polled > now

    async def test_updates_statuses_on_a_full_work_pool(
        self,
        client,
        session,
        work_queues,
        work_pools,
        flow,
    ):
        async def create_deployment_for_work_queue(work_queue_id):
            return await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name="My Deployment",
                    tags=["test"],
                    flow_id=flow.id,
                    work_queue_id=work_queue_id,
                ),
            )

        work_pool = work_pools["wp_a"]

        wq_not_ready = work_queues["wq_aa"]
        wq_not_ready.status = WorkQueueStatus.NOT_READY

        wq_paused = work_queues["wq_ab"]
        wq_paused.status = WorkQueueStatus.PAUSED

        wq_ready = work_queues["wq_ac"]
        wq_ready.status = WorkQueueStatus.READY

        deployments = [
            await create_deployment_for_work_queue(wq.id)
            for wq in (wq_not_ready, wq_paused, wq_ready)
        ]

        await session.commit()

        poll_response = await client.post(
            f"/work_pools/{work_pool.name}/get_scheduled_flow_runs",
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queues_response = await client.post(
            f"/work_pools/{work_pool.name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = parse_obj_as(List[WorkQueue], work_queues_response.json())

        for work_queue in work_queues:
            if work_queue.id == wq_not_ready.id:
                assert work_queue.status == WorkQueueStatus.READY
            elif work_queue.id == wq_paused.id:
                # paused work queues should stay paused
                assert work_queue.status == WorkQueueStatus.PAUSED
            elif work_queue.id == wq_ready.id:
                assert work_queue.status == WorkQueueStatus.READY

        for deployment in deployments:
            await session.refresh(deployment)
            assert deployment.status == DeploymentStatus.READY

    async def test_ensure_deployments_associated_with_work_pool_have_deployment_status_of_ready(
        self, client, work_pools, deployment
    ):
        assert deployment.last_polled is None
        deployment_response = await client.get(f"/deployments/{deployment.id}")
        assert deployment_response.status_code == status.HTTP_200_OK
        assert deployment_response.json()["status"] == "NOT_READY"

        # trigger a poll of the work queue, which should update the deployment status
        deployment_work_pool_name = work_pools["wp_a"].name
        queue_response = await client.post(
            f"/work_pools/{deployment_work_pool_name}/get_scheduled_flow_runs",
        )
        assert queue_response.status_code == status.HTTP_200_OK

        # get the updated deployment
        updated_deployment_response = await client.get(f"/deployments/{deployment.id}")
        assert updated_deployment_response.status_code == status.HTTP_200_OK
        assert updated_deployment_response.json()["status"] == "READY"
