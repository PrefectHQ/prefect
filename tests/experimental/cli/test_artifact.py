import pendulum
import pytest

from prefect.server import models, schemas
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def auto_enable_artifacts(enable_artifacts):
    """
    Enable artifacts for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS
    # Import to register artifact CLI
    import prefect.experimental.cli.artifact  # noqa


@pytest.fixture
async def artifact(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data={"a": 1}, type="table", description="opens many doors"
    )
    model = (
        await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        ),
    )

    await session.commit()

    return model[0]


@pytest.fixture
async def artifact_null_field(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_={"description": "opens many doors"}
    )
    model = (
        await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        ),
    )

    await session.commit()

    return model[0]


@pytest.fixture
async def artifacts(session):
    model1 = await models.artifacts.create_artifact(
        session=session,
        artifact=schemas.core.Artifact(
            key="voltaic", data=1, description="opens many doors", type="table"
        ),
    )
    model2 = await models.artifacts.create_artifact(
        session=session,
        artifact=schemas.core.Artifact(
            key="voltaic", data=2, description="opens many doors", type="table"
        ),
    )
    model3 = await models.artifacts.create_artifact(
        session=session,
        artifact=schemas.core.Artifact(
            key="lotus", data=3, description="opens many doors", type="markdown"
        ),
    )

    await session.commit()

    return [model1, model2, model3]


def test_listing_artifacts_when_none_exist():
    invoke_and_assert(
        ["artifact", "ls"],
        expected_output_contains=f"""
            ┏━━━━┳━━━━━┳━━━━━━┳━━━━━━━━━┓
            ┃ ID ┃ Key ┃ Type ┃ Updated ┃
            ┡━━━━╇━━━━━╇━━━━━━╇━━━━━━━━━┩
            └────┴─────┴──────┴─────────┘
        """,
    )


def test_listing_artifacts_after_creating_artifacts(artifact):
    invoke_and_assert(
        ["artifact", "ls"],
        expected_output_contains=f"""
            ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
            ┃                                   ID ┃ Key     ┃ Type  ┃ Updated           ┃
            ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
            │ {artifact.id} │ {artifact.key} │ {artifact.type} │ {pendulum.instance(artifact.updated).diff_for_humans()} │
            └──────────────────────────────────────┴─────────┴───────┴───────────────────┘
            """,
    )


def test_listing_artifacts_after_creating_artifacts_with_null_fields(
    artifact_null_field,
):
    artifact = artifact_null_field
    invoke_and_assert(
        ["artifact", "ls"],
        expected_output_contains=f"""
            ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
            ┃                                   ID ┃ Key     ┃ Type ┃ Updated           ┃
            ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
            │ {artifact.id} │ {artifact.key} │      │ {pendulum.instance(artifact.updated).diff_for_humans()} │
            └──────────────────────────────────────┴─────────┴──────┴───────────────────┘
            """,
    )


def test_listing_artifacts_with_limit(
    artifacts,
):
    expected_output = artifacts[2].key
    invoke_and_assert(
        ["artifact", "ls", "--limit", "1"],
        expected_output_contains=expected_output,
        expected_code=0,
    )


def test_listing_artifacts_lists_only_latest_versions(artifacts):
    expected_output = (
        f"{artifacts[2].id}",
        f"{artifacts[1].id}",
    )

    invoke_and_assert(
        ["artifact", "ls"],
        expected_output_contains=expected_output,
        expected_output_does_not_contain=f"{artifacts[0].id}",
        expected_code=0,
    )


def test_inspecting_artifact_succeeds(artifacts):
    """
    We expect to see all versions of the artifact.
    """
    expected_output = (
        f"{artifacts[0].id}",
        f"{artifacts[0].key}",
        f"{artifacts[0].type}",
        f"{artifacts[0].description}",
        f"{artifacts[0].data}",
        f"{artifacts[1].id}",
        f"{artifacts[1].key}",
        f"{artifacts[1].type}",
        f"{artifacts[1].description}",
        f"{artifacts[1].data}",
    )

    invoke_and_assert(
        ["artifact", "inspect", str(artifacts[0].key)],
        expected_output_contains=expected_output,
        expected_code=0,
        expected_output_does_not_contain=f"{artifacts[2].id}",
    )


def test_inspecting_artifact_nonexistent_key_raises():
    invoke_and_assert(
        ["artifact", "inspect", "nonexistent_key"],
        expected_output_contains="Artifact 'nonexistent_key' not found",
        expected_code=1,
    )


def test_inspecting_artifact_with_limit(artifacts):
    expected_output = (
        f"{artifacts[1].key}",
        f"{artifacts[1].data}",
    )  # most recently updated
    invoke_and_assert(
        ["artifact", "inspect", str(artifacts[0].key), "--limit", "1"],
        expected_output_contains=expected_output,
        expected_output_does_not_contain=(f"{artifacts[0].id}", f"{artifacts[2].id}"),
        expected_code=0,
    )
