"""Tests for the database vacuum docket task functions."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.actions import LogCreate
from prefect.server.services.db_vacuum import (
    vacuum_old_flow_runs,
    vacuum_orphaned_artifacts,
    vacuum_orphaned_logs,
    vacuum_stale_artifact_collections,
)
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now


@pytest.fixture(autouse=True)
def enable_db_vacuum(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable the vacuum service and set short retention for testing."""
    settings = get_current_settings()
    monkeypatch.setattr(settings.server.services.db_vacuum, "enabled", True)
    monkeypatch.setattr(
        settings.server.services.db_vacuum,
        "retention_period",
        timedelta(days=1),
    )
    monkeypatch.setattr(settings.server.services.db_vacuum, "batch_size", 100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OLD = now("UTC") - timedelta(days=30)
RECENT = now("UTC") - timedelta(hours=1)


async def _create_flow_run(
    session,
    flow,
    *,
    state=None,
    end_time=None,
    parent_task_run_id=None,
):
    if state is None:
        state = schemas.states.Completed()
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=state,
            end_time=end_time,
            parent_task_run_id=parent_task_run_id,
        ),
    )
    await session.commit()
    return flow_run


async def _create_task_run(session, flow_run):
    task_run = await models.task_runs.create_task_run(
        session=session,
        task_run=schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id,
            task_key=f"task-{uuid.uuid4()}",
            dynamic_key="0",
        ),
    )
    await session.commit()
    return task_run


async def _create_log(session, flow_run_id=None, task_run_id=None):
    await models.logs.create_logs(
        session=session,
        logs=[
            LogCreate(
                name="prefect.test",
                level=20,
                message="test log",
                timestamp=now("UTC"),
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
            ),
        ],
    )
    await session.commit()


async def _create_artifact(session, flow_run_id=None, key=None):
    artifact = await models.artifacts.create_artifact(
        session=session,
        artifact=schemas.core.Artifact(
            key=key,
            data=1,
            flow_run_id=flow_run_id,
        ),
    )
    await session.commit()
    return artifact


async def _count(session, db: PrefectDBInterface, model) -> int:
    result = await session.execute(sa.select(sa.func.count(model.id)))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestVacuumOldFlowRuns:
    async def test_deletes_old_completed_flow_runs(self, session, flow):
        """Old terminal flow runs should be deleted."""
        db = provide_database_interface()
        await _create_flow_run(session, flow, end_time=OLD)

        assert await _count(session, db, db.FlowRun) == 1
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0

    async def test_preserves_recent_flow_runs(self, session, flow):
        """Flow runs within the retention period should not be deleted."""
        db = provide_database_interface()
        await _create_flow_run(session, flow, end_time=RECENT)

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 1

    async def test_preserves_running_flow_runs(self, session, flow):
        """Non-terminal flow runs should never be deleted."""
        db = provide_database_interface()
        await _create_flow_run(
            session,
            flow,
            state=schemas.states.Running(),
            end_time=None,
        )

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 1

    async def test_cascade_deletes_task_runs(self, session, flow):
        """Task runs belonging to a deleted flow run should be cascade-deleted."""
        db = provide_database_interface()
        flow_run = await _create_flow_run(session, flow, end_time=OLD)
        await _create_task_run(session, flow_run)

        assert await _count(session, db, db.TaskRun) == 1
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0
            assert await _count(new_session, db, db.TaskRun) == 0

    async def test_subflow_cleaned_up_with_parent(self, session, flow):
        """Old subflows are cleaned up when their parent is deleted (same vacuum run)."""
        db = provide_database_interface()
        parent = await _create_flow_run(session, flow, end_time=OLD)
        parent_task = await _create_task_run(session, parent)

        # Subflow: old, terminal, has parent_task_run_id
        await _create_flow_run(
            session,
            flow,
            end_time=OLD,
            parent_task_run_id=parent_task.id,
        )

        assert await _count(session, db, db.FlowRun) == 2

        # Parent deletion cascades SET NULL on subflow's parent_task_run_id,
        # making it top-level. The batch loop's next iteration picks it up.
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0

    async def test_recent_subflow_survives_parent_deletion(self, session, flow):
        """A recent subflow survives even after its parent is deleted."""
        db = provide_database_interface()
        parent = await _create_flow_run(session, flow, end_time=OLD)
        parent_task = await _create_task_run(session, parent)

        # Subflow: recent end_time, so not eligible for deletion
        subflow = await _create_flow_run(
            session,
            flow,
            end_time=RECENT,
            parent_task_run_id=parent_task.id,
        )

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            # Parent deleted, but subflow survives (too recent)
            result = await new_session.execute(
                sa.select(db.FlowRun).where(db.FlowRun.id == subflow.id)
            )
            remaining = result.scalar_one_or_none()
            assert remaining is not None
            assert remaining.parent_task_run_id is None  # SET NULL by cascade

    async def test_deletes_all_terminal_states(self, session, flow):
        """All terminal state types should be eligible for deletion."""
        db = provide_database_interface()
        for state_cls in (
            schemas.states.Completed,
            schemas.states.Failed,
            schemas.states.Cancelled,
            schemas.states.Crashed,
        ):
            await _create_flow_run(session, flow, state=state_cls(), end_time=OLD)

        assert await _count(session, db, db.FlowRun) == 4
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0

    async def test_preserves_terminal_run_without_end_time(self, session, flow):
        """Terminal flow runs with end_time=None should not be deleted."""
        db = provide_database_interface()
        await _create_flow_run(
            session, flow, state=schemas.states.Completed(), end_time=None
        )

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 1

    async def test_preserves_scheduled_flow_runs(self, session, flow):
        """Scheduled (non-terminal) flow runs should not be deleted."""
        db = provide_database_interface()
        await _create_flow_run(
            session, flow, state=schemas.states.Scheduled(), end_time=None
        )

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 1

    async def test_preserves_cancelling_flow_runs(self, session, flow):
        """CANCELLING is non-terminal and should not be deleted."""
        db = provide_database_interface()
        await _create_flow_run(
            session, flow, state=schemas.states.Cancelling(), end_time=OLD
        )

        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 1


class TestVacuumOrphanedLogs:
    async def test_deletes_orphaned_logs(self, session, flow):
        """Logs referencing a non-existent flow run should be deleted."""
        db = provide_database_interface()
        # Create a log pointing to a flow_run_id that doesn't exist
        fake_flow_run_id = uuid.uuid4()
        await _create_log(session, flow_run_id=fake_flow_run_id)

        assert await _count(session, db, db.Log) == 1
        await vacuum_orphaned_logs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Log) == 0

    async def test_preserves_logs_with_existing_flow_run(self, session, flow):
        """Logs tied to an existing flow run should not be deleted."""
        db = provide_database_interface()
        flow_run = await _create_flow_run(session, flow, end_time=RECENT)
        await _create_log(session, flow_run_id=flow_run.id)

        await vacuum_orphaned_logs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Log) == 1

    async def test_preserves_logs_with_null_flow_run_id(self, session, flow):
        """Logs with flow_run_id=NULL (e.g. task-run-only) should not be deleted."""
        db = provide_database_interface()
        await _create_log(session, flow_run_id=None)

        await vacuum_orphaned_logs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Log) == 1


class TestVacuumOrphanedArtifacts:
    async def test_deletes_orphaned_artifacts(self, session, flow):
        """Artifacts referencing a non-existent flow run should be deleted."""
        db = provide_database_interface()
        fake_flow_run_id = uuid.uuid4()
        await _create_artifact(session, flow_run_id=fake_flow_run_id)

        assert await _count(session, db, db.Artifact) == 1
        await vacuum_orphaned_artifacts(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Artifact) == 0

    async def test_preserves_artifacts_with_existing_flow_run(self, session, flow):
        """Artifacts tied to an existing flow run should not be deleted."""
        db = provide_database_interface()
        flow_run = await _create_flow_run(session, flow, end_time=RECENT)
        await _create_artifact(session, flow_run_id=flow_run.id)

        await vacuum_orphaned_artifacts(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Artifact) == 1

    async def test_preserves_artifacts_with_null_flow_run_id(self, session, flow):
        """Artifacts with flow_run_id=NULL should not be deleted."""
        db = provide_database_interface()
        await _create_artifact(session, flow_run_id=None)

        await vacuum_orphaned_artifacts(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Artifact) == 1


class TestVacuumArtifactCollections:
    async def test_deletes_stale_artifact_collections(self, session, flow):
        """Artifact collections pointing to deleted artifacts should be removed."""
        db = provide_database_interface()
        # Create an artifact with a key -> this also creates an artifact_collection
        fake_flow_run_id = uuid.uuid4()
        await _create_artifact(session, flow_run_id=fake_flow_run_id, key="my-report")

        assert await _count(session, db, db.ArtifactCollection) == 1

        # First vacuum orphaned artifacts, then stale collections
        await vacuum_orphaned_artifacts(db=db)
        await vacuum_stale_artifact_collections(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.Artifact) == 0
            assert await _count(new_session, db, db.ArtifactCollection) == 0

    async def test_repoints_collection_to_next_latest_version(self, session, flow):
        """When the latest artifact is orphaned but an older version exists,
        the collection should be re-pointed to the older version."""
        db = provide_database_interface()
        # Older artifact version — tied to an existing flow run
        live_run = await _create_flow_run(session, flow, end_time=RECENT)
        older_artifact = await _create_artifact(
            session, flow_run_id=live_run.id, key="my-report"
        )

        # Newer artifact version (same key) — orphaned flow run
        fake_flow_run_id = uuid.uuid4()
        await _create_artifact(session, flow_run_id=fake_flow_run_id, key="my-report")

        # Collection should point to the newer (orphaned) artifact
        assert await _count(session, db, db.ArtifactCollection) == 1

        await vacuum_orphaned_artifacts(db=db)
        await vacuum_stale_artifact_collections(db=db)

        async with db.session_context() as new_session:
            # Orphaned artifact deleted, but collection survives re-pointed
            assert await _count(new_session, db, db.Artifact) == 1
            assert await _count(new_session, db, db.ArtifactCollection) == 1

            # Verify collection now points to the older (surviving) artifact
            result = await new_session.execute(
                sa.select(db.ArtifactCollection).where(
                    db.ArtifactCollection.key == "my-report"
                )
            )
            collection = result.scalar_one()
            assert collection.latest_id == older_artifact.id

    async def test_deletes_standalone_stale_collection(self, session):
        """A stale collection row (e.g. left over from a previous crash)
        should be deleted even without artifact cleanup in the same cycle."""
        db = provide_database_interface()
        # Directly insert a collection row with a dangling latest_id
        async with db.session_context(begin_transaction=True) as s:
            await s.execute(
                sa.insert(db.ArtifactCollection).values(
                    id=uuid.uuid4(),
                    key="stale-key",
                    latest_id=uuid.uuid4(),  # points to nothing
                )
            )

        async with db.session_context() as s:
            assert await _count(s, db, db.ArtifactCollection) == 1

        await vacuum_stale_artifact_collections(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.ArtifactCollection) == 0

    async def test_preserves_valid_artifact_collections(self, session, flow):
        """Artifact collections pointing to existing artifacts should be preserved."""
        db = provide_database_interface()
        flow_run = await _create_flow_run(session, flow, end_time=RECENT)
        await _create_artifact(session, flow_run_id=flow_run.id, key="my-report")

        await vacuum_stale_artifact_collections(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.ArtifactCollection) == 1


class TestVacuumBatching:
    async def test_batching_deletes_all_records(self, session, flow, monkeypatch):
        """With batch_size=5, all 12 old flow runs should eventually be deleted."""
        settings = get_current_settings()
        monkeypatch.setattr(settings.server.services.db_vacuum, "batch_size", 5)

        db = provide_database_interface()
        for _ in range(12):
            await _create_flow_run(session, flow, end_time=OLD)

        assert await _count(session, db, db.FlowRun) == 12
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0


class TestVacuumIdempotency:
    async def test_second_run_is_noop(self, session, flow):
        """Running vacuum tasks twice should produce zero changes on the second run."""
        db = provide_database_interface()
        await _create_flow_run(session, flow, end_time=OLD)
        fake_flow_run_id = uuid.uuid4()
        await _create_log(session, flow_run_id=fake_flow_run_id)
        await _create_artifact(session, flow_run_id=fake_flow_run_id, key="report")

        await vacuum_orphaned_logs(db=db)
        await vacuum_orphaned_artifacts(db=db)
        await vacuum_stale_artifact_collections(db=db)
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0
            assert await _count(new_session, db, db.Log) == 0
            assert await _count(new_session, db, db.Artifact) == 0
            assert await _count(new_session, db, db.ArtifactCollection) == 0

        # Second run should be a no-op
        await vacuum_orphaned_logs(db=db)
        await vacuum_orphaned_artifacts(db=db)
        await vacuum_stale_artifact_collections(db=db)
        await vacuum_old_flow_runs(db=db)

        async with db.session_context() as new_session:
            assert await _count(new_session, db, db.FlowRun) == 0
            assert await _count(new_session, db, db.Log) == 0
            assert await _count(new_session, db, db.Artifact) == 0
            assert await _count(new_session, db, db.ArtifactCollection) == 0


class TestNoOp:
    async def test_empty_database_does_not_error(self):
        """Running vacuum tasks on an empty database should complete without error."""
        db = provide_database_interface()
        await vacuum_orphaned_logs(db=db)
        await vacuum_orphaned_artifacts(db=db)
        await vacuum_stale_artifact_collections(db=db)
        await vacuum_old_flow_runs(db=db)
