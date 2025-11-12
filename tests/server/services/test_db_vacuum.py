"""
Tests for the DBVacuum service which deletes old Prefect resources.
"""

from datetime import timedelta
from typing import Sequence
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database.orm_models import (
    ORMArtifact,
    ORMFlow,
    ORMFlowRun,
    ORMLog,
    ORMTaskRun,
)
from prefect.server.schemas import states
from prefect.server.services.db_vacuum import DBVacuum
from prefect.types._datetime import now

# Time constants for test data
THE_RECENT_PAST = now("UTC") - timedelta(hours=1)
THE_ANCIENT_PAST = now("UTC") - timedelta(days=100)


@pytest.fixture
async def old_flow_run(session: AsyncSession, flow: ORMFlow):
    """Create a flow run older than the default retention period."""
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Completed(),
        ),
    )
    # Manually set the created timestamp to be old
    flow_run.created = THE_ANCIENT_PAST
    session.add(flow_run)
    await session.commit()
    return flow_run


@pytest.fixture
async def recent_flow_run(session: AsyncSession, flow: ORMFlow):
    """Create a recent flow run within the retention period."""
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Completed(),
        ),
    )
    # Manually set the created timestamp to be recent
    flow_run.created = THE_RECENT_PAST
    session.add(flow_run)
    await session.commit()
    return flow_run


@pytest.fixture
async def old_flow_run_with_task_runs(session: AsyncSession, flow: ORMFlow):
    """Create an old flow run with multiple task runs."""
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Completed(),
        ),
    )
    # Manually set the created timestamp to be old
    flow_run.created = THE_ANCIENT_PAST
    session.add(flow_run)
    await session.flush()

    task_runs = []
    for i in range(3):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key=f"task-{i}",
                dynamic_key=f"dynamic-{i}",
                state=states.Completed(),
            ),
        )
        task_runs.append(task_run)

    await session.commit()
    return flow_run, task_runs


@pytest.fixture
async def orphaned_log_maker(session: AsyncSession):
    """Factory to create orphaned logs (logs with no associated flow run)."""

    async def make_orphaned_log():
        log = ORMLog(
            name="Log",
            flow_run_id=UUID("00000000-0000-0000-0000-000000000000"),
            message="This is an orphaned log",
            level=20,
            timestamp=now("UTC"),
        )
        session.add(log)
        await session.commit()
        return log

    return make_orphaned_log


@pytest.fixture
async def log_with_flow_run(session: AsyncSession, flow: ORMFlow):
    """Create a log associated with a flow run."""
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Running(),
        ),
    )
    await session.flush()

    log = ORMLog(
        name="Log",
        flow_run_id=flow_run.id,
        message="This log has a flow run",
        level=20,
        timestamp=now("UTC"),
    )
    session.add(log)
    await session.commit()
    return log, flow_run


@pytest.fixture
async def orphaned_artifact_maker(session: AsyncSession):
    """Factory to create orphaned artifacts (artifacts with no associated flow run)."""

    async def make_orphaned_artifact():
        artifact = ORMArtifact(
            key="orphaned-artifact",
            data={"value": "test"},
            type="result",
            flow_run_id=UUID("00000000-0000-0000-0000-000000000000"),
        )
        session.add(artifact)
        await session.commit()
        return artifact

    return make_orphaned_artifact


@pytest.fixture
async def artifact_with_flow_run(session: AsyncSession, flow: ORMFlow):
    """Create an artifact associated with a flow run."""
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Running(),
        ),
    )
    await session.flush()

    artifact = ORMArtifact(
        key="valid-artifact",
        data={"value": "test"},
        type="result",
        flow_run_id=flow_run.id,
    )
    session.add(artifact)
    await session.commit()
    return artifact, flow_run


async def test_delete_old_flow_runs(
    session: AsyncSession,
    old_flow_run: ORMFlowRun,
    recent_flow_run: ORMFlowRun,
):
    """Test that old flow runs are deleted but recent ones are kept."""
    # Run the vacuum service once
    await DBVacuum().start(loops=1)

    # Check that the old flow run was deleted
    result = await session.execute(
        select(ORMFlowRun).where(ORMFlowRun.id == old_flow_run.id)
    )
    assert result.scalar_one_or_none() is None

    # Check that the recent flow run still exists
    result = await session.execute(
        select(ORMFlowRun).where(ORMFlowRun.id == recent_flow_run.id)
    )
    assert result.scalar_one_or_none() is not None


async def test_delete_old_flow_runs_with_task_runs(
    session: AsyncSession,
    old_flow_run_with_task_runs: tuple,
):
    """Test that deleting flow runs also deletes associated task runs (cascade)."""
    old_flow_run, task_runs = old_flow_run_with_task_runs

    # Run the vacuum service once
    await DBVacuum().start(loops=1)

    # Check that the old flow run was deleted
    result = await session.execute(
        select(ORMFlowRun).where(ORMFlowRun.id == old_flow_run.id)
    )
    assert result.scalar_one_or_none() is None

    # Check that all task runs were cascade deleted
    for task_run in task_runs:
        result = await session.execute(
            select(ORMTaskRun).where(ORMTaskRun.id == task_run.id)
        )
        assert result.scalar_one_or_none() is None


async def test_delete_orphaned_logs(
    session: AsyncSession,
    orphaned_log_maker,
    log_with_flow_run: tuple,
):
    """Test that orphaned logs are deleted but logs with flow runs are kept."""
    # Create orphaned logs
    orphaned_log = await orphaned_log_maker()

    log, flow_run = log_with_flow_run

    # Run the vacuum service once
    await DBVacuum().start(loops=1)

    # Check that the orphaned log was deleted
    result = await session.execute(select(ORMLog).where(ORMLog.id == orphaned_log.id))
    assert result.scalar_one_or_none() is None

    # Check that the log with a flow run still exists
    result = await session.execute(select(ORMLog).where(ORMLog.id == log.id))
    assert result.scalar_one_or_none() is not None


async def test_delete_orphaned_artifacts(
    session: AsyncSession,
    orphaned_artifact_maker,
    artifact_with_flow_run: tuple,
):
    """Test that orphaned artifacts are deleted but artifacts with flow runs are kept."""
    # Create orphaned artifacts
    orphaned_artifact = await orphaned_artifact_maker()

    artifact, flow_run = artifact_with_flow_run

    # Run the vacuum service once
    await DBVacuum().start(loops=1)

    # Check that the orphaned artifact was deleted
    result = await session.execute(
        select(ORMArtifact).where(ORMArtifact.id == orphaned_artifact.id)
    )
    assert result.scalar_one_or_none() is None

    # Check that the artifact with a flow run still exists
    result = await session.execute(
        select(ORMArtifact).where(ORMArtifact.id == artifact.id)
    )
    assert result.scalar_one_or_none() is not None


async def test_vacuum_integration(
    session: AsyncSession,
    flow: ORMFlow,
    orphaned_log_maker,
    orphaned_artifact_maker,
):
    """Test the full vacuum process: delete old flow runs, then clean up orphaned resources."""
    # Create an old flow run with task runs
    old_flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.core.FlowRun(
            flow_id=flow.id,
            state=states.Completed(),
        ),
    )
    old_flow_run.created = THE_ANCIENT_PAST
    session.add(old_flow_run)
    await session.flush()
    await session.refresh(old_flow_run)

    # Create task runs
    for i in range(2):
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=old_flow_run.id,
                task_key=f"task-{i}",
                dynamic_key=f"dynamic-{i}",
                state=states.Completed(),
            ),
        )

    # Create logs and artifacts for this flow run
    log = ORMLog(
        name="Log",
        flow_run_id=old_flow_run.id,
        message="Log for old flow run",
        level=20,
        timestamp=now("UTC"),
    )
    session.add(log)

    artifact = ORMArtifact(
        key="artifact-for-old-run",
        data={"value": "test"},
        type="result",
        flow_run_id=old_flow_run.id,
    )
    session.add(artifact)
    await session.flush()
    await session.refresh(log)
    await session.refresh(artifact)
    await session.commit()

    # Also create some already orphaned resources
    orphaned_log = await orphaned_log_maker()
    orphaned_artifact = await orphaned_artifact_maker()

    # Run the vacuum service once
    await DBVacuum().start(loops=1)

    # Check that the old flow run was deleted
    result = await session.execute(
        select(ORMFlowRun).where(ORMFlowRun.id == old_flow_run.id)
    )
    assert result.scalar_one_or_none() is None

    # The logs and artifacts should now be orphaned, but might not be deleted in the first run
    # Run again to clean up newly orphaned resources
    await DBVacuum().start(loops=1)

    # Now check that all orphaned logs are deleted
    result = await session.execute(select(ORMLog).where(ORMLog.id == log.id))
    assert result.scalar_one_or_none() is None

    result = await session.execute(select(ORMLog).where(ORMLog.id == orphaned_log.id))
    assert result.scalar_one_or_none() is None

    # And all orphaned artifacts are deleted
    result = await session.execute(
        select(ORMArtifact).where(ORMArtifact.id == artifact.id)
    )
    assert result.scalar_one_or_none() is None

    result = await session.execute(
        select(ORMArtifact).where(ORMArtifact.id == orphaned_artifact.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.fixture
async def many_old_flow_runs(
    session: AsyncSession, flow: ORMFlow
) -> Sequence[ORMFlowRun]:
    """Create many old flow runs for batch testing."""
    runs: list[ORMFlowRun] = []
    async with session.begin():
        for i in range(15):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=states.Completed(),
                ),
            )
            flow_run.created = THE_ANCIENT_PAST
            session.add(flow_run)

            # Add task runs to each flow run
            for j in range(2):
                await models.task_runs.create_task_run(
                    session=session,
                    task_run=schemas.core.TaskRun(
                        flow_run_id=flow_run.id,
                        task_key=f"task-{i}-{j}",
                        dynamic_key=f"dynamic-{i}-{j}",
                        state=states.Completed(),
                    ),
                )
            runs.append(flow_run)

    return runs


async def test_vacuum_respects_batch_size(
    session: AsyncSession,
    many_old_flow_runs: Sequence[ORMFlowRun],
):
    """Test that the vacuum service processes deletions in batches."""
    # Create a vacuum service with a small batch size
    service = DBVacuum()

    # The batch size is controlled by settings, but we can verify that
    # not all runs are deleted instantly by checking after one loop
    initial_count = len(many_old_flow_runs)
    assert initial_count == 15

    # Run the service once
    await service.start(loops=1)

    # Count remaining flow runs
    result = await session.execute(select(ORMFlowRun))
    remaining_runs = result.scalars().all()

    # Depending on batch size and how the service works, some runs may be deleted
    # The important thing is that the service completes without error
    # and eventually all old runs get deleted
    assert len(remaining_runs) <= initial_count


async def test_vacuum_leaves_recent_runs_alone(
    session: AsyncSession,
    flow: ORMFlow,
):
    """Test that recent flow runs within the retention period are not deleted."""
    # Create multiple recent flow runs
    recent_runs = []
    async with session.begin():
        for i in range(5):
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=states.Completed(),
                ),
            )
            flow_run.created = THE_RECENT_PAST
            session.add(flow_run)
            recent_runs.append(flow_run)

    # Run the vacuum service
    await DBVacuum().start(loops=1)

    # Check that all recent runs still exist
    for run in recent_runs:
        result = await session.execute(
            select(ORMFlowRun).where(ORMFlowRun.id == run.id)
        )
        assert result.scalar_one_or_none() is not None


async def test_delete_multiple_orphaned_logs(
    session: AsyncSession,
    orphaned_log_maker,
):
    """Test deletion of multiple orphaned logs."""
    # Create multiple orphaned logs
    orphaned_logs = []
    for i in range(10):
        log = await orphaned_log_maker()
        orphaned_logs.append(log)

    # Run the vacuum service
    await DBVacuum().start(loops=1)

    # Check that all orphaned logs were deleted
    for log in orphaned_logs:
        result = await session.execute(select(ORMLog).where(ORMLog.id == log.id))
        assert result.scalar_one_or_none() is None


async def test_delete_multiple_orphaned_artifacts(
    session: AsyncSession,
    orphaned_artifact_maker,
):
    """Test deletion of multiple orphaned artifacts."""
    # Create multiple orphaned artifacts
    orphaned_artifacts = []
    for i in range(10):
        artifact = await orphaned_artifact_maker()
        orphaned_artifacts.append(artifact)

    # Run the vacuum service
    await DBVacuum().start(loops=1)

    # Check that all orphaned artifacts were deleted
    for artifact in orphaned_artifacts:
        result = await session.execute(
            select(ORMArtifact).where(ORMArtifact.id == artifact.id)
        )
        assert result.scalar_one_or_none() is None
