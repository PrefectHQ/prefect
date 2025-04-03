from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models
from prefect.server.api.ui.task_runs import TaskRunCount
from prefect.server.database import orm_models
from prefect.server.schemas import core, filters, states
from prefect.types import DateTime


class TestReadDashboardTaskRunCounts:
    @pytest.fixture
    def url(self) -> str:
        return "/ui/task_runs/dashboard/counts"

    @pytest.fixture
    def time_window(self) -> tuple[datetime, datetime]:
        now = datetime(2023, 6, 1, 18, tzinfo=timezone.utc)
        return (now, now - timedelta(hours=8))

    @pytest.fixture
    def task_run_filter(
        self, time_window: tuple[DateTime, DateTime]
    ) -> filters.TaskRunFilter:
        now, eight_hours_ago = time_window
        return filters.TaskRunFilter(
            start_time=filters.TaskRunFilterStartTime(
                after_=eight_hours_ago, before_=now
            )
        )

    @pytest.fixture
    async def create_task_runs(
        self,
        session: AsyncSession,
        flow_run: orm_models.FlowRun,
        time_window: tuple[DateTime, DateTime],
    ):
        now, eight_hours_ago = time_window
        runs_to_create = 100
        time_gap = (now - eight_hours_ago) / runs_to_create

        for i in range(runs_to_create):
            if i % 2 == 0:
                state_type = states.StateType.COMPLETED
                state_name = "Completed"
            else:
                state_type = states.StateType.FAILED
                state_name = "Failed"

            await models.task_runs.create_task_run(
                session=session,
                task_run=core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key=f"task-{i}",
                    dynamic_key=str(i),
                    state_type=state_type,
                    state_name=state_name,
                    start_time=eight_hours_ago + (i * time_gap),
                    end_time=eight_hours_ago + (i * time_gap),
                ),
            )

        await session.commit()

    async def test_requires_task_run_filter_start_time(
        self,
        url: str,
        client: AsyncClient,
    ):
        task_run_filter = filters.TaskRunFilter()
        response = await client.post(
            url, json={"task_runs": task_run_filter.model_dump(mode="json")}
        )
        assert response.status_code == 422
        assert b"task_runs.start_time.after_ is required" in response.content

    async def test_empty_state(
        self,
        url: str,
        task_run_filter: filters.TaskRunFilter,
        client: AsyncClient,
    ):
        response = await client.post(
            url, json={"task_runs": task_run_filter.model_dump(mode="json")}
        )
        assert response.status_code == 200

        counts = [TaskRunCount(**count) for count in response.json()]
        assert counts == [
            TaskRunCount(completed=0, failed=0) for _ in range(len(counts))
        ]

    @pytest.mark.usefixtures("create_task_runs")
    async def test_returns_completed_and_failed_counts(
        self,
        url: str,
        task_run_filter: filters.TaskRunFilter,
        client: AsyncClient,
    ):
        response = await client.post(
            url, json={"task_runs": task_run_filter.model_dump(mode="json")}
        )
        assert response.status_code == 200

        counts = [TaskRunCount(**count) for count in response.json()]

        assert counts == [
            TaskRunCount(completed=3, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=3, failed=2),
            TaskRunCount(completed=2, failed=3),
            TaskRunCount(completed=2, failed=2),
        ]


class TestReadTaskRunCountsByState:
    @pytest.fixture
    def url(self) -> str:
        return "/ui/task_runs/count"

    @pytest.fixture
    async def create_flow_runs(
        self,
        session: AsyncSession,
        flow: orm_models.Flow,
    ):
        await session.execute(delete(orm_models.FlowRun))

        run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=core.FlowRun(
                flow_id=flow.id,
                state=states.Completed(),
            ),
        )

        run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=core.FlowRun(
                flow_id=flow.id,
                state=states.Failed(),
            ),
        )

        run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=core.FlowRun(
                flow_id=flow.id,
                state=states.Pending(),
            ),
        )

        await session.commit()

        yield [run_1, run_2, run_3]

    @pytest.fixture
    async def create_task_runs(
        self,
        session: AsyncSession,
        flow_run: orm_models.FlowRun,
        create_flow_runs: list[orm_models.FlowRun],
    ):
        await session.execute(delete(orm_models.TaskRun))

        task_runs_per_flow_run = 27
        now = cast(DateTime, datetime(2023, 6, 1, 18, tzinfo=timezone.utc))

        for flow_run in create_flow_runs:
            for i in range(task_runs_per_flow_run):
                # This means that each flow run should have task runs with the following states:
                # 9 completed, 9 failed, 3 scheduled, 3 running, 2 cancelled, 1 crashed, 1 paused, 1 cancelling, 1 pending
                if i < 9:
                    state_type = states.StateType.COMPLETED
                    state_name = "Completed"
                elif i < 15:
                    state_type = states.StateType.FAILED
                    state_name = "Failed"
                elif i < 18:
                    state_type = states.StateType.SCHEDULED
                    state_name = "Scheduled"
                elif i < 21:
                    state_type = states.StateType.RUNNING
                    state_name = "Running"
                elif i < 23:
                    state_type = states.StateType.CANCELLED
                    state_name = "Cancelled"
                elif i < 24:
                    state_type = states.StateType.CRASHED
                    state_name = "Crashed"
                elif i < 25:
                    state_type = states.StateType.PAUSED
                    state_name = "Paused"
                elif i < 26:
                    state_type = states.StateType.CANCELLING
                    state_name = "Cancelling"
                else:
                    state_type = states.StateType.PENDING
                    state_name = "Pending"

                await models.task_runs.create_task_run(
                    session=session,
                    task_run=core.TaskRun(
                        flow_run_id=flow_run.id,
                        task_key=f"task-{i}-{uuid4()}",
                        dynamic_key=str(uuid4()),
                        state_type=state_type,
                        state_name=state_name,
                        start_time=now,
                        end_time=now,
                    ),
                )

        await session.commit()

        yield

    async def test_returns_all_state_types(
        self,
        url: str,
        client: AsyncClient,
    ):
        response = await client.post(url)
        assert response.status_code == 200

        counts = response.json()

        assert set(counts.keys()) == set(states.StateType.__members__.keys())

    async def test_none(
        self,
        url: str,
        client: AsyncClient,
        session: AsyncSession,
    ):
        # ensure there are no task runs in the database
        await session.execute(delete(orm_models.TaskRun))
        await session.commit()

        response = await client.post(url)
        assert response.status_code == 200

        counts = response.json()
        assert counts == {
            "COMPLETED": 0,
            "FAILED": 0,
            "PENDING": 0,
            "RUNNING": 0,
            "CANCELLED": 0,
            "CRASHED": 0,
            "PAUSED": 0,
            "CANCELLING": 0,
            "SCHEDULED": 0,
        }

    @pytest.mark.usefixtures("create_task_runs")
    async def test_returns_counts(
        self,
        url: str,
        client: AsyncClient,
    ):
        response = await client.post(url)
        assert response.status_code == 200

        counts = response.json()

        assert counts == {
            "COMPLETED": 9 * 3,
            "FAILED": 6 * 3,
            "PENDING": 1 * 3,
            "RUNNING": 3 * 3,
            "CANCELLED": 2 * 3,
            "CRASHED": 1 * 3,
            "PAUSED": 1 * 3,
            "CANCELLING": 1 * 3,
            "SCHEDULED": 3 * 3,
        }

    @pytest.mark.usefixtures("create_task_runs")
    async def test_returns_counts_with_filter(
        self,
        url: str,
        client: AsyncClient,
    ):
        response = await client.post(
            url,
            json={
                "flow_runs": filters.FlowRunFilter(
                    state=filters.FlowRunFilterState(
                        type=filters.FlowRunFilterStateType(
                            any_=[states.StateType.COMPLETED]
                        )
                    )
                ).model_dump(mode="json")
            },
        )

        assert response.status_code == 200

        counts = response.json()

        assert counts == {
            "COMPLETED": 9,
            "FAILED": 6,
            "PENDING": 1,
            "RUNNING": 3,
            "CANCELLED": 2,
            "CRASHED": 1,
            "PAUSED": 1,
            "CANCELLING": 1,
            "SCHEDULED": 3,
        }


class TestReadTaskRun:
    async def test_read_task_run(
        self,
        flow_run: orm_models.FlowRun,
        task_run: orm_models.TaskRun,
        client: AsyncClient,
    ):
        response = await client.get(f"/ui/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(task_run.id)
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["flow_run_name"] == flow_run.name

    async def test_read_task_without_flow_run(
        self, task_run_without_flow_run: orm_models.TaskRun, client: AsyncClient
    ):
        response = await client.get(f"/ui/task_runs/{task_run_without_flow_run.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(task_run_without_flow_run.id)
        assert response.json()["flow_run_id"] is None
        assert response.json()["flow_run_name"] is None

    async def test_read_task_run_returns_404_if_does_not_exist(
        self, client: AsyncClient
    ):
        response = await client.get(f"/ui/task_runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
