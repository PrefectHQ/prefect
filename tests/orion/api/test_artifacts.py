from typing import List
from uuid import uuid4

import pendulum
import pydantic
import pytest
from fastapi import status

from prefect.orion import models, schemas
from prefect.orion.schemas import actions
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS, temporary_settings


@pytest.fixture
async def create_artifacts(flow_run, task_run, client):
    artifact_1 = actions.ArtifactCreate(
        key="artifact-1", data=1, flow_run_id=flow_run.id, task_run_id=task_run.id
    ).dict(json_compatible=True)
    await client.post("/experimental/artifacts/", json=artifact_1)

    artifact_2 = actions.ArtifactCreate(
        key="artifact-2", flow_run_id=flow_run.id, task_run_id=task_run.id
    ).dict(json_compatible=True)
    await client.post("/experimental/artifacts/", json=artifact_2)

    artifact_3 = actions.ArtifactCreate(key="artifact-3", flow_run_id=flow_run.id).dict(
        json_compatible=True
    )
    await client.post("/experimental/artifacts/", json=artifact_3)


@pytest.fixture(autouse=True)
def auto_enable_artifacts(enable_artifacts):
    """
    Enable artifacts for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS


class TestEnableArtifactsFlag:
    async def test_flag_defaults_to_false(self):
        with temporary_settings(
            restore_defaults={PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS}
        ):
            assert not PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS

    async def test_404_when_flag_disabled(self, client):
        with temporary_settings(
            restore_defaults={PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS}
        ):
            response = await client.post(
                "/experimental/artifacts/", json=dict(key="black-lotus")
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateArtifact:
    async def test_create_artifact(self, flow_run, task_run, client):
        response = await client.post(
            "/experimental/artifacts/",
            json=actions.ArtifactCreate(
                key="voltaic",
                data=1,
                metadata_="opens many doors",
                flow_run_id=flow_run.id,
                task_run_id=task_run.id,
            ).dict(json_compatible=True),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["key"] == "voltaic"
        assert response.json()["data"] == 1
        assert response.json()["metadata_"] == "opens many doors"
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["task_run_id"] == str(task_run.id)


class TestReadArtifact:
    @pytest.fixture
    async def artifact(self, session, flow_run, task_run):

        artifact_schema = schemas.core.Artifact(
            key="voltaic",
            data=1,
            metadata_="opens many doors",
            flow_run_id=flow_run.id,
            task_run_id=task_run.id,
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )
        await session.commit()
        yield artifact

    async def test_read_artifact(self, artifact, client):
        response = await client.get(f"/experimental/artifacts/{artifact.id}")
        assert response.status_code == status.HTTP_200_OK

    async def test_read_artifact_not_found(self, client):
        response = await client.get(f"/experimental/artifacts/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadArtifacts:
    async def test_read_artifacts(self, create_artifacts, client):
        response = await client.post("/experimental/artifacts/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3
        result = pydantic.parse_obj_as(List[schemas.core.Artifact], response.json())

        sorted([r.key for r in result]) == ["artifact-1", "artifact-2", "artifact-3"]

    async def test_read_artifacts_with_applies_filter(
        self, create_artifacts, flow_run, client
    ):
        artifact_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(any_=["artifact-1", "artifact-2"])
            ).dict(json_compatible=True)
        )
        response = await client.post(
            "/experimental/artifacts/filter", json=artifact_filter
        )
        assert response.status_code == status.HTTP_200_OK
        assert all(
            [item["flow_run_id"] == str(flow_run.id) for item in response.json()]
        )
        assert len(response.json()) == 2

    async def test_read_artifacts_with_flow_run_filter(
        self, create_artifacts, flow_run, client
    ):
        flow_run_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                flow_run_id=schemas.filters.ArtifactFilterFlowRunId(any_=[flow_run.id])
            ).dict(json_compatible=True)
        )
        response = await client.post(
            "/experimental/artifacts/filter", json=flow_run_filter
        )
        assert response.status_code == status.HTTP_200_OK
        assert all(
            [item["flow_run_id"] == str(flow_run.id) for item in response.json()]
        )

    async def test_read_artifacts_with_task_run_filter(
        self, create_artifacts, task_run, client
    ):
        task_run_filter = dict(
            artifacts=schemas.filters.ArtifactFilter(
                task_run_id=schemas.filters.ArtifactFilterTaskRunId(any_=[task_run.id])
            ).dict(json_compatible=True)
        )
        response = await client.post(
            "/experimental/artifacts/filter", json=task_run_filter
        )
        assert response.status_code == status.HTTP_200_OK
        assert all(
            [item["task_run_id"] == str(task_run.id) for item in response.json()]
        )

    async def test_read_artifacts_with_multiple_filters(
        self, create_artifacts, flow_run, task_run, client
    ):
        multiple_filters = dict(
            artifacts=schemas.filters.ArtifactFilter(
                flow_run_id=schemas.filters.ArtifactFilterFlowRunId(any_=[flow_run.id]),
                task_run_id=schemas.filters.ArtifactFilterTaskRunId(any_=[task_run.id]),
            ).dict(json_compatible=True),
        )
        response = await client.post(
            "/experimental/artifacts/filter", json=multiple_filters
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert all(
            [item["flow_run_id"] == str(flow_run.id) for item in response.json()]
        )
        assert all(
            [item["task_run_id"] == str(task_run.id) for item in response.json()]
        )

    async def test_read_artifacts_with_limit(self, create_artifacts, client):
        response = await client.post(
            "/experimental/artifacts/filter", json={"limit": 1}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_artifacts_with_offset(self, create_artifacts, client):
        response = await client.post(
            "/experimental/artifacts/filter",
            json={
                "offset": 1,
                "sort": schemas.sorting.ArtifactSort.KEY_DESC,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2
        assert [r["key"] for r in response.json()] == ["artifact-2", "artifact-1"]

    async def test_read_artifacts_with_sort(self, create_artifacts, client):
        response = await client.post(
            "/experimental/artifacts/filter",
            json=dict(sort=schemas.sorting.ArtifactSort.UPDATED_DESC),
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3
        assert [r["key"] for r in response.json()] == [
            "artifact-3",
            "artifact-2",
            "artifact-1",
        ]

    async def test_read_artifacts_returns_empty_list(self, client):
        response = await client.post("/experimental/artifacts/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0


class TestUpdateArtifact:
    async def test_update_artifact_succeeds(self, create_artifacts, client):
        response = await client.post("/experimental/artifacts/filter")
        now = pendulum.now("utc")
        assert response.status_code == status.HTTP_200_OK
        artifact_id = response.json()[0]["id"]
        artifact_key = response.json()[0]["key"]
        artifact_flow_run_id = response.json()[0]["flow_run_id"]

        response = await client.patch(
            f"/experimental/artifacts/{artifact_id}",
            json={"data": {"new": "data"}},
        )

        assert response.status_code == 204

        response = await client.get(f"/experimental/artifacts/{artifact_id}")
        updated_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        assert updated_artifact.data == {"new": "data"}
        assert updated_artifact.key == artifact_key
        assert str(updated_artifact.flow_run_id) == artifact_flow_run_id
        assert updated_artifact.created < now
        assert updated_artifact.updated > now

    async def test_update_artifact_does_not_update_if_fields_are_not_set(
        self, create_artifacts, client
    ):
        response = await client.post("/experimental/artifacts/filter")
        now = pendulum.now("utc")
        assert response.status_code == status.HTTP_200_OK
        artifact_id = response.json()[0]["id"]
        artifact_key = response.json()[0]["key"]
        artifact_flow_run_id = response.json()[0]["flow_run_id"]
        artifact_data = response.json()[0]["data"]

        response = await client.patch(
            f"/experimental/artifacts/{artifact_id}",
            json={},
        )

        assert response.status_code == 204

        response = await client.get(f"/experimental/artifacts/{artifact_id}")
        updated_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        assert updated_artifact.data == artifact_data
        assert updated_artifact.key == artifact_key
        assert str(updated_artifact.flow_run_id) == artifact_flow_run_id
        assert updated_artifact.created < now
        assert updated_artifact.updated > now

    async def test_update_artifact_raises_error_if_artifact_not_found(
        self, create_artifacts, client
    ):
        response = await client.patch(
            f"/experimental/artifacts/{str(uuid4())}",
            json={"data": {"new": "data"}},
        )

        assert response.status_code == 404
