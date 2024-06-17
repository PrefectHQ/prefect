from uuid import uuid4

import pytest

from prefect.server import models, schemas
from prefect.server.schemas import actions


@pytest.fixture
async def artifact(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_={"description": "opens many doors"}
    )
    artifact = await models.artifacts.create_artifact(
        session=session, artifact=artifact_schema
    )
    await session.commit()
    return artifact


@pytest.fixture
async def artifacts(flow_run, task_run, session):
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


@pytest.fixture
async def deployment_artifacts(deployment, session):
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=deployment.flow_id,
            deployment_id=deployment.id,
            flow_version="1.0",
        ),
    )
    artifact1_schema = schemas.core.Artifact(
        key="voltaic1",
        data=1,
        metadata_={"description": "opens many doors"},
        flow_run_id=flow_run.id,
    )
    artifact1 = await models.artifacts.create_artifact(
        session=session, artifact=artifact1_schema
    )

    artifact2_schema = schemas.core.Artifact(
        key="voltaic1",
        data=2,
        metadata_={"description": "opens many doors"},
        flow_run_id=flow_run.id,
    )
    artifact2 = await models.artifacts.create_artifact(
        session=session, artifact=artifact2_schema
    )

    return [flow_run, artifact1, artifact2]


@pytest.fixture
async def flow_artifacts(session):
    flow = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name="my-flow", tags=["green"])
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
        ),
    )
    artifact1_schema = schemas.core.Artifact(
        key="voltaic2",
        data=1,
        metadata_={"description": "opens many doors"},
        flow_run_id=flow_run.id,
    )
    artifact1 = await models.artifacts.create_artifact(
        session=session, artifact=artifact1_schema
    )

    artifact2_schema = schemas.core.Artifact(
        key="voltaic2",
        data=2,
        metadata_={"description": "opens many doors"},
        flow_run_id=flow_run.id,
    )
    artifact2 = await models.artifacts.create_artifact(
        session=session, artifact=artifact2_schema
    )

    return [flow, artifact1, artifact2]


class TestCreateArtifacts:
    async def test_creating_artifacts(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_={"description": "opens many doors"}
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )
        assert artifact.key == "voltaic"
        assert artifact.data == 1
        assert artifact.metadata_ == {"description": "opens many doors"}

    async def test_creating_artifact_with_key_succeeds_and_upsert_to_artifact_collection(
        self, artifact, session
    ):
        assert await models.artifacts.read_artifact(session, artifact.id)

        artifact_collection_result = await models.artifacts.read_latest_artifact(
            key=artifact.key, session=session
        )
        assert artifact_collection_result.latest_id == artifact.id

    async def test_creating_artifact_without_key_arg_does_not_upsert_to_artifact_collection(
        self, session
    ):
        artifact_schema = schemas.core.Artifact(
            key=None,
            data=1,
            description="Some info about my artifact",
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )
        assert artifact.id is not None
        assert artifact.key == artifact_schema.key
        assert artifact.data == artifact_schema.data
        assert artifact.description == artifact_schema.description

    async def test_creating_artifact_with_existing_key_appends_in_artifact_and_upserts_in_artifact_collection(
        self, artifact, session
    ):
        artifact_collection_result = await models.artifacts.read_latest_artifact(
            session=session, key=artifact.key
        )
        assert artifact_collection_result.latest_id == artifact.id
        assert artifact_collection_result.key == artifact.key
        assert artifact_collection_result.updated == artifact_collection_result.created

        new_artifact_schema = schemas.core.Artifact(
            key=artifact.key,
            data=2,
            description="Some info about my artifact",
        )
        new_artifact = await models.artifacts.create_artifact(
            session=session,
            artifact=new_artifact_schema,
        )

        assert await models.artifacts.read_artifact(
            session=session,
            artifact_id=artifact.id,
        )
        assert await models.artifacts.read_artifact(
            session=session,
            artifact_id=new_artifact.id,
        )

        new_artifact_version = await models.artifacts.read_latest_artifact(
            session=session,
            key=artifact.key,
        )

        assert new_artifact_version.latest_id == new_artifact.id

    async def test_creating_artifact_with_null_key_does_not_upsert_to_artifact_collection(
        self, session
    ):
        artifact_schema = schemas.core.Artifact(
            data=1,
            description="Some info about my artifact",
        )
        artifact = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact_schema,
        )

        assert await models.artifacts.read_artifact(
            session=session,
            artifact_id=artifact.id,
        )

        assert not await models.artifacts.read_latest_artifact(
            session=session,
            key=artifact_schema.key,
        )


class TestCountArtifacts:
    async def test_count_artifacts(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_={"description": "opens many doors"}
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )
        assert artifact.key == "voltaic"

        count = await models.artifacts.count_artifacts(session=session)

        assert count == 1

    async def test_counting_single_artifact(self, artifact, session):
        count = await models.artifacts.count_artifacts(session=session)

        assert count == 1

    async def test_counting_artifacts_with_artifact_filter(self, artifacts, session):
        artifact_filter = schemas.filters.ArtifactFilter(
            key=schemas.filters.ArtifactFilterKey(any_=[artifacts[0].key])
        )
        count = await models.artifacts.count_artifacts(
            session=session, artifact_filter=artifact_filter
        )

        assert count == 1

    async def test_counting_artifacts_by_with_flow_run_filter(self, artifacts, session):
        flow_run_filter = schemas.filters.FlowRunFilter(
            id=schemas.filters.FlowRunFilterId(any_=[artifacts[0].flow_run_id])
        )
        count = await models.artifacts.count_artifacts(
            session=session, flow_run_filter=flow_run_filter
        )

        assert count == 2

    async def test_counting_artifacts_by_with_task_run_filter(self, artifacts, session):
        task_run_filter = schemas.filters.TaskRunFilter(
            id=schemas.filters.TaskRunFilterId(any_=[artifacts[0].task_run_id])
        )
        count = await models.artifacts.count_artifacts(
            session=session, task_run_filter=task_run_filter
        )

        assert count == 2

    async def test_counting_artifacts_by_flow_name(self, flow_artifacts, session):
        flow_name = flow_artifacts[0].name
        result = await models.artifacts.count_artifacts(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ),
        )
        assert result == 2

    async def test_counting_artifacts_by_deployment(
        self, deployment_artifacts, session
    ):
        deployment_id = deployment_artifacts[0].deployment_id
        result = await models.artifacts.count_artifacts(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ),
        )
        assert result == 2

    async def test_counting_latest_artifacts_by_flow_name(
        self, flow_artifacts, session
    ):
        flow_name = flow_artifacts[0].name
        result = await models.artifacts.count_latest_artifacts(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ),
        )
        assert result == 1

    async def test_counting_latest_artifacts_by_deployment(
        self, deployment_artifacts, session
    ):
        deployment_id = deployment_artifacts[0].deployment_id
        result = await models.artifacts.count_latest_artifacts(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ),
        )
        assert result == 1


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

    @pytest.fixture
    async def progress_artifact(self, session):
        artifact_schema = schemas.core.Artifact(
            type="progress",
            data=0.0,
            description="Info about the progress artifact",
        )
        artifact = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact_schema,
        )

        await session.commit()
        yield artifact

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

    async def test_update_artifact_succeeds_with_data_and_without_key(
        self, progress_artifact, session
    ):
        new_data = 50.00
        assert await models.artifacts.update_artifact(
            session=session,
            artifact_id=progress_artifact.id,
            artifact=actions.ArtifactUpdate(data=new_data),
        )

        updated_artifact = await models.artifacts.read_artifact(
            session=session,
            artifact_id=progress_artifact.id,
        )

        assert updated_artifact.data == new_data


class TestReadLatestArtifact:
    async def test_reading_artifact_by_key(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, description="opens many doors"
        )
        artifact = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact_schema,
        )

        assert artifact.key == "voltaic"

        tutored_artifact = await models.artifacts.read_latest_artifact(
            session=session, key=artifact.key
        )
        assert tutored_artifact.latest_id == artifact.id
        assert tutored_artifact.key == "voltaic"
        assert tutored_artifact.data == 1
        assert tutored_artifact.description == "opens many doors"


class TestReadLatestArtifacts:
    @pytest.fixture
    async def artifacts(self, session, flow_run, task_run):
        artifacts = [
            schemas.core.Artifact(
                key="key-1",
                data=1,
                type="markdown",
                flow_run_id=flow_run.id,
                description="Some info about my artifact",
            ),
            schemas.core.Artifact(
                key="key-1",
                data=2,
                type="markdown",
                flow_run_id=flow_run.id,
                description="Some info about my artifact",
            ),
            schemas.core.Artifact(
                key="key-2",
                data=3,
                type="table",
                flow_run_id=flow_run.id,
                task_run_id=task_run.id,
                description="Some info about my artifact",
            ),
            schemas.core.Artifact(
                key="key-3",
                data=4,
                type="table",
                description="Some info about my artifact",
            ),
        ]
        for artifact_schema in artifacts:
            await models.artifacts.create_artifact(
                session=session,
                artifact=artifact_schema,
            )

        return artifacts

    async def test_read_latest_artifacts(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
        )

        assert len(read_artifacts) == 3
        assert {a.key for a in read_artifacts} == {"key-1", "key-2", "key-3"}
        assert {a.data for a in read_artifacts} == {2, 3, 4}

    async def test_read_latest_artifacts_with_artifact_type_filter(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
            artifact_filter=schemas.filters.ArtifactCollectionFilter(
                type=schemas.filters.ArtifactCollectionFilterType(any_=["table"]),
            ),
        )
        assert len(read_artifacts) == 2

        assert {a.key for a in read_artifacts} == {"key-2", "key-3"}
        assert {a.data for a in read_artifacts} == {3, 4}

    async def test_read_latest_artifacts_with_artifact_key_filter(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
            artifact_filter=schemas.filters.ArtifactCollectionFilter(
                key=schemas.filters.ArtifactCollectionFilterKey(any_=["key-1"]),
            ),
        )

        assert len(read_artifacts) == 1

        assert artifacts[1].id == read_artifacts[0].latest_id

    async def test_read_latest_artifacts_with_flow_run_id_filter(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
            artifact_filter=schemas.filters.ArtifactCollectionFilter(
                flow_run_id=schemas.filters.ArtifactCollectionFilterFlowRunId(
                    any_=[artifacts[0].flow_run_id]
                ),
            ),
            sort=schemas.sorting.ArtifactCollectionSort.KEY_ASC,
        )

        assert len(read_artifacts) == 2
        assert artifacts[1].id == read_artifacts[0].latest_id
        assert artifacts[2].id == read_artifacts[1].latest_id

    async def test_read_latest_artifacts_with_task_run_id_filter(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
            artifact_filter=schemas.filters.ArtifactCollectionFilter(
                task_run_id=schemas.filters.ArtifactCollectionFilterTaskRunId(
                    any_=[artifacts[2].task_run_id]
                ),
            ),
        )

        assert len(read_artifacts) == 1
        assert artifacts[2].id == read_artifacts[0].latest_id

    async def test_read_latest_artifacts_with_limit(
        self,
        artifacts,
        session,
    ):
        read_artifacts = await models.artifacts.read_latest_artifacts(
            session=session,
            limit=1,
            sort=schemas.sorting.ArtifactCollectionSort.KEY_DESC,
            artifact_filter=schemas.filters.ArtifactCollectionFilter(),
        )

        assert len(read_artifacts) == 1
        assert read_artifacts[0].key == artifacts[-1].key

    async def test_reading_latest_artifacts_by_flow_name(self, flow_artifacts, session):
        flow_name = flow_artifacts[0].name
        result = await models.artifacts.read_latest_artifacts(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ),
        )
        assert len(result) == 1
        assert result[0].latest_id == flow_artifacts[2].id

    async def test_reading_latest_artifacts_by_deployment(
        self, deployment_artifacts, session
    ):
        deployment_id = deployment_artifacts[0].deployment_id
        result = await models.artifacts.read_latest_artifacts(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ),
        )
        assert len(result) == 1
        assert result[0].latest_id == deployment_artifacts[2].id


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

    async def test_reading_artifacts_by_flow_name(self, flow_artifacts, session):
        flow_name = flow_artifacts[0].name
        result = await models.artifacts.read_artifacts(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=[flow_name])
            ),
        )
        assert len(result) == len(flow_artifacts) - 1
        assert sorted([result[0].id, result[1].id]) == sorted(
            [flow_artifacts[1].id, flow_artifacts[2].id]
        )

    async def test_reading_artifacts_by_deployment(self, deployment_artifacts, session):
        deployment_id = deployment_artifacts[0].deployment_id
        result = await models.artifacts.read_artifacts(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment_id])
            ),
        )
        assert len(result) == len(deployment_artifacts) - 1
        assert sorted([result[0].id, result[1].id]) == sorted(
            [deployment_artifacts[1].id, deployment_artifacts[2].id]
        )

    async def test_reading_artifacts_returns_empty_list_if_missing(self, session):
        tutored_artifacts = await models.artifacts.read_artifacts(session)

        assert len(tutored_artifacts) == 0


class TestDeleteArtifacts:
    @pytest.fixture
    async def artifacts(
        self,
        session,
    ):
        # Create several artifacts with the same key
        artifact1_schema = schemas.core.Artifact(
            key="test-key-1",
            data="my important data",
            description="Info about the artifact",
        )
        artifact1 = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact1_schema,
        )

        artifact2_schema = schemas.core.Artifact(
            key="test-key-1",
            data="my important data",
            description="Info about the artifact",
        )
        artifact2 = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact2_schema,
        )

        artifact3_schema = schemas.core.Artifact(
            key="test-key-1",
            data="my important data",
            description="Info about the artifact",
        )
        artifact3 = await models.artifacts.create_artifact(
            session=session,
            artifact=artifact3_schema,
        )

        await session.commit()
        return [artifact1, artifact2, artifact3]

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

    async def test_delete_only_artifact_version_deletes_row_in_artifact_and_artifact_collection(
        self,
        artifact,
        session,
    ):
        assert await models.artifacts.delete_artifact(
            session=session, artifact_id=artifact.id
        )
        assert not await models.artifacts.read_artifact(
            session=session, artifact_id=artifact.id
        )

        assert not await models.artifacts.read_latest_artifact(
            session=session, key=artifact.key
        )

    async def test_delete_earliest_artifact_deletes_row_in_artifact_and_ignores_artifact_collection(
        self,
        artifacts,
        session,
    ):
        assert await models.artifacts.delete_artifact(
            session=session, artifact_id=artifacts[0].id
        )
        assert not await models.artifacts.read_artifact(
            session=session, artifact_id=artifacts[0].id
        )

        artifact_collection_result = await models.artifacts.read_latest_artifact(
            session=session, key=artifacts[1].key
        )

        assert artifact_collection_result.latest_id == artifacts[-1].id

    async def test_delete_middle_artifact_deletes_row_in_artifact_and_ignores_artifact_collection(
        self, artifacts, session
    ):
        assert await models.artifacts.delete_artifact(
            session=session, artifact_id=artifacts[1].id
        )

        assert not await models.artifacts.read_artifact(
            session=session, artifact_id=artifacts[1].id
        )

        artifact_collection_result = await models.artifacts.read_latest_artifact(
            session=session, key=artifacts[-1].key
        )

        assert artifact_collection_result.latest_id == artifacts[-1].id

    async def test_delete_latest_artifact_deletes_row_in_artifact_and_updates_artifact_collection(
        self, artifacts, session
    ):
        assert await models.artifacts.delete_artifact(
            session=session, artifact_id=artifacts[2].id
        )

        assert not await models.artifacts.read_artifact(
            session=session, artifact_id=artifacts[2].id
        )

        artifact_collection_result = await models.artifacts.read_latest_artifact(
            session=session, key=artifacts[1].key
        )

        assert artifact_collection_result.latest_id == artifacts[1].id
