from uuid import uuid4

from prefect.server import models, schemas


async def test_creating_artifacts(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_="opens many doors"
    )
    artifact = await models.artifacts.create_artifact(
        session=session, artifact=artifact_schema
    )
    assert artifact.key == "voltaic"
    assert artifact.data == 1
    assert artifact.metadata_ == "opens many doors"


class TestReadingSingleArtifacts:
    async def test_reading_artifacts_by_id(self, session):
        artifact_schema = schemas.core.Artifact(
            key="voltaic", data=1, metadata_="opens many doors"
        )
        artifact = await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        )

        artifact_id = artifact.id
        tutored_artifact = await models.artifacts.read_artifact(session, artifact_id)

        assert tutored_artifact.key == "voltaic"
        assert tutored_artifact.data == 1
        assert tutored_artifact.metadata_ == "opens many doors"

    async def test_reading_artifacts_returns_none_if_missing(self, session):
        tutored_artifact = await models.artifacts.read_artifact(session, str(uuid4()))

        assert tutored_artifact is None
