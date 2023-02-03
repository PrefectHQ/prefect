from uuid import uuid4

import pytest
from fastapi import status

from prefect.orion import models, schemas


# create a fixture for the artifact so that test_read_artifact works
@pytest.fixture
async def artifact(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_="opens many doors"
    )
    artifact = await models.artifacts.create_artifact(
        session=session, artifact=artifact_schema
    )
    yield artifact


class TestCreateArtifact:
    async def test_create_artifact(self, flow_run, task_run, session, client):
        artifact_data = {
            "key": "voltaic",
            "data": 1,
            "metadata_": "opens many doors",
            "flow_run_id": str(flow_run.id),
            "task_run_id": str(task_run.id),
        }
        response = await client.post("/artifacts/", json=artifact_data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["key"] == "voltaic"
        assert response.json()["data"] == 1
        assert response.json()["metadata_"] == "opens many doors"
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["task_run_id"] == str(task_run.id)


class TestReadArtifact:
    @pytest.fixture
    async def artifact(self, session):
        artifact = await models.artifacts.create_artifact(
            session=session,
            artifact=schemas.core.Artifact(
                key="voltaic", data=1, metadata_="opens many doors"
            ),
        )
        await session.commit()
        yield artifact

    async def test_read_artifact(self, artifact, client):
        response = await client.get(f"/artifacts/{artifact.id}")
        assert response.status_code == status.HTTP_200_OK

    async def test_read_artifact_not_found(self, client):
        response = await client.get(f"/artifacts/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
