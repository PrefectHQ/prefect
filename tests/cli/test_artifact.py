import sys
from uuid import uuid4

import pendulum
import pytest
from typer import Exit

from prefect.server import models, schemas
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.artifact.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


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
        expected_output_contains="""
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


def test_listing_artifacts_with_all_set_to_true(artifacts):
    expected_output = (
        f"{artifacts[0].id}",
        f"{artifacts[1].id}",
        f"{artifacts[2].id}",
    )

    invoke_and_assert(
        ["artifact", "ls", "--all"],
        expected_output_contains=expected_output,
        expected_code=0,
    )


def test_listing_artifacts_with_all_set_to_false(artifacts):
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


def test_deleting_artifact_by_key_succeeds(artifacts):
    invoke_and_assert(
        ["artifact", "delete", str(artifacts[0].key)],
        prompts_and_responses=[
            ("Are you sure you want to delete 2 artifact(s) with key 'voltaic'?", "y"),
        ],
        expected_output_contains="Deleted 2 artifact(s) with key 'voltaic'.",
        expected_code=0,
    )


def test_deleting_artifact_nonexistent_key_raises():
    nonexistent_key = "nonexistent_key"
    invoke_and_assert(
        ["artifact", "delete", nonexistent_key],
        user_input="y",
        expected_output_contains=f"Artifact with key '{nonexistent_key}' not found.",
        expected_code=1,
    )


def test_deleting_artifact_by_key_without_confimation_aborts(artifacts):
    invoke_and_assert(
        ["artifact", "delete", str(artifacts[0].key)],
        user_input="n",
        expected_output_contains="Deletion aborted.",
        expected_code=1,
    )


def test_deleting_artifact_by_id_succeeds(artifacts):
    invoke_and_assert(
        ["artifact", "delete", "--id", str(artifacts[0].id)],
        user_input="y",
        expected_output_contains="Deleted artifact",
        expected_code=0,
    )


def test_deleting_artifact_nonexistent_id_raises():
    fake_artifact_id = str(uuid4())
    invoke_and_assert(
        ["artifact", "delete", "--id", fake_artifact_id],
        user_input="y",
        expected_output_contains=f"Artifact with id '{fake_artifact_id}' not found",
        expected_code=1,
    )


def test_deleting_artifact_by_id_without_confimation_aborts(artifacts):
    invoke_and_assert(
        ["artifact", "delete", "--id", str(artifacts[0].id)],
        user_input="n",
        expected_output_contains="Deletion aborted.",
        expected_code=1,
    )


def test_deleting_artifact_with_key_and_id_raises(artifacts):
    invoke_and_assert(
        ["artifact", "delete", artifacts[1].key, "--id", artifacts[1].id],
        expected_output_contains=(
            "Please provide either a key or an artifact_id but not both."
        ),
        expected_code=1,
    )


def test_deleting_artifact_without_key_or_id_raises(artifacts):
    invoke_and_assert(
        ["artifact", "delete"],
        expected_output_contains="Please provide a key or an artifact_id.",
        expected_code=1,
    )
