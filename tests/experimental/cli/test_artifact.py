import pendulum
import pytest

from prefect.server import models, schemas
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def auto_enable_artifacts(enable_artifacts):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS
    # Import to register worker CLI
    import prefect.experimental.cli.artifact  # noqa


@pytest.fixture
async def artifact(session):
    artifact_schema = schemas.core.Artifact(
        key="voltaic", data=1, metadata_={"description": "opens many doors"}
    )
    model = (
        await models.artifacts.create_artifact(
            session=session, artifact=artifact_schema
        ),
    )

    await session.commit()

    read_artifact = await models.artifacts.read_artifact(
        session=session, artifact_id=model[0].id
    )

    return read_artifact


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
            ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
            ┃                                   ID ┃ Key     ┃ Type ┃ Updated           ┃
            ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
            │ {artifact.id} │ {artifact.key} │ {artifact.type} │ {pendulum.instance(artifact.updated).diff_for_humans()} │
            └──────────────────────────────────────┴─────────┴──────┴───────────────────┘
            """,
    )
