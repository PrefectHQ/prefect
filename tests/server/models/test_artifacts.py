from uuid import uuid4

import pytest

from prefect.server import models, schemas
from prefect.server.schemas import actions


async def test_creating_artifacts(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_={"description": "opens many doors"}
    )
    artifact = await models.artifacts.create_artifact(
        session=session, artifact=artifact_schema
    )
    assert artifact.key == "voltaic"
    assert artifact.data == 1
    assert artifact.metadata_ == {"description": "opens many doors"}


class TestUpdateArtifacts:
    @pytest.fixture
    async def artifact(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_={"description": "opens many doors"}
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )
        await session.commit()
        return artifact

    async def test_update_artifact_succeeds(self, artifact, session):
        artifact_id = artifact.id
        updated_result = await models.artifacts.update_artifact(
            session=session,
            artifact_id=artifact_id,
            artifact=actions.ArtifactUpdate(data=2),
        )

        assert updated_result

        updated_artifact = await models.artifacts.read_artifact(session, artifact_id)
        assert updated_artifact.data == 2

    async def test_update_artifact_fails_if_missing(self, session):
        updated_result = await models.artifacts.update_artifact(
            session=session,
            artifact_id=str(uuid4()),
            artifact=actions.ArtifactUpdate(data=2),
        )
        assert not updated_result

    async def test_update_artifact_does_not_update_if_fields_not_set(
        self, artifact, session
    ):
        artifact_id = artifact.id
        updated_result = await models.artifacts.update_artifact(
            session=session, artifact_id=artifact_id, artifact=actions.ArtifactUpdate()
        )
        assert updated_result

        updated_artifact = await models.artifacts.read_artifact(session, artifact_id)
        assert updated_artifact.data == 1


class TestReadingSingleArtifacts:
    async def test_reading_artifacts_by_id(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_={"description": "opens many doors"}
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )

        artifact_id = artifact.id
        tutored_artifact = await models.artifacts.read_artifact(session, artifact_id)

        assert tutored_artifact.key == "voltaic"
        assert tutored_artifact.data == 1
        assert tutored_artifact.metadata_ == {"description": "opens many doors"}

    async def test_reading_artifacts_returns_none_if_missing(self, session):
        tutored_artifact = await models.artifacts.read_artifact(session, str(uuid4()))

        assert tutored_artifact is None


class TestReadingMultipleArtifacts:
    @pytest.fixture
    async def artifacts(self, flow_run, task_run, session):
        # create 3 artifacts w/ diff keys
        artifact1_schema = schemas.core.Artifact(
            key="voltaic1",
            data=1,
            metadata_={"description": "opens many doors"},
            flow_run_id=flow_run.id,
            task_run_id=task_run.id,
        )
        artifact1 = await models.artifacts.create_artifact(
            session=session, artifact=artifact1_schema
        )

        artifact2_schema = schemas.core.Artifact(
            key="voltaic2",
            data=2,
            metadata_={"description": "opens many doors"},
            flow_run_id=flow_run.id,
            task_run_id=task_run.id,
        )
        artifact2 = await models.artifacts.create_artifact(
            session=session, artifact=artifact2_schema
        )

        artifact3_schema = schemas.core.Artifact(
            key="voltaic3",
            data=3,
            metadata_={"description": "opens many doors"},
        )
        artifact3 = await models.artifacts.create_artifact(
            session=session, artifact=artifact3_schema
        )
        yield [artifact1, artifact2, artifact3]

    async def test_reading_artifacts_by_ids(self, artifacts, session):
        artifact_ids = [artifact.id for artifact in artifacts]
        artifact_filter = schemas.filters.ArtifactFilter(
            id=schemas.filters.ArtifactFilterId(
                any_=[artifact_ids[0], artifact_ids[1], artifact_ids[2]]
            )
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, artifact_filter=artifact_filter
        )

        assert len(tutored_artifacts) == 3
        assert tutored_artifacts[0].id in artifact_ids
        assert tutored_artifacts[1].id in artifact_ids
        assert tutored_artifacts[2].id in artifact_ids

    async def test_reading_artifacts_by_keys(self, artifacts, session):
        artifact_keys = [artifact.key for artifact in artifacts]
        artifact_filter = schemas.filters.ArtifactFilter(
            key=schemas.filters.ArtifactFilterKey(
                any_=[artifact_keys[1], artifact_keys[2]]
            )
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, artifact_filter=artifact_filter
        )

        assert len(tutored_artifacts) == 2
        assert tutored_artifacts[0].key in artifact_keys
        assert tutored_artifacts[1].key in artifact_keys

    async def test_reading_artifacts_by_flow_run_id(self, artifacts, session):
        flow_run_ids = [artifact.flow_run_id for artifact in artifacts]
        artifact_filter = schemas.filters.ArtifactFilter(
            flow_run_id=schemas.filters.ArtifactFilterFlowRunId(any_=[flow_run_ids[1]])
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, artifact_filter=artifact_filter
        )

        assert len(tutored_artifacts) == 2
        assert tutored_artifacts[0].flow_run_id == flow_run_ids[1]
        assert tutored_artifacts[1].flow_run_id == flow_run_ids[1]

    async def test_reading_artifacts_by_task_run_id(self, artifacts, session):
        task_run_ids = [artifact.task_run_id for artifact in artifacts]
        artifact_filter = schemas.filters.ArtifactFilter(
            task_run_id=schemas.filters.ArtifactFilterTaskRunId(
                any_=[task_run_ids[0], task_run_ids[1]]
            )
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, artifact_filter=artifact_filter
        )

        assert len(tutored_artifacts) == 2
        assert tutored_artifacts[0].task_run_id == task_run_ids[0]
        assert tutored_artifacts[1].task_run_id == task_run_ids[1]

    async def test_reading_artifacts_by_flow_run(self, artifacts, session):
        flow_run_ids = [artifact.flow_run_id for artifact in artifacts]
        flow_run_filter = schemas.filters.FlowRunFilter(
            id=schemas.filters.FlowRunFilterId(any_=[flow_run_ids[0]])
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, flow_run_filter=flow_run_filter
        )

        assert len(tutored_artifacts) == 2
        assert tutored_artifacts[0].flow_run_id == flow_run_ids[0]

    async def test_reading_artifacts_by_task_run(self, artifacts, session):
        task_run_ids = [artifact.task_run_id for artifact in artifacts]
        task_run_filter = schemas.filters.TaskRunFilter(
            id=schemas.filters.TaskRunFilterId(any_=[task_run_ids[0]])
        )
        tutored_artifacts = await models.artifacts.read_artifacts(
            session, task_run_filter=task_run_filter
        )

        assert len(tutored_artifacts) == 2
        assert tutored_artifacts[0].task_run_id == task_run_ids[0]

    async def test_reading_artifacts_flow_run_filter_returns_empty_list_if_missing(
        self, session
    ):
        tutored_artifacts = await models.artifacts.read_artifacts(session)

        assert len(tutored_artifacts) == 0


class TestDeleteArtifacts:
    async def test_delete_artifact_succeeds(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_={"description": "opens many doors"}
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )

        artifact_id = artifact.id
        deleted_result = await models.artifacts.delete_artifact(session, artifact_id)

        assert deleted_result

        deleted_artifact = await models.artifacts.read_artifact(session, artifact_id)
        assert deleted_artifact is None

    async def test_delete_artifact_fails_if_missing(self, session):
        deleted_result = await models.artifacts.delete_artifact(session, str(uuid4()))

        assert not deleted_result
