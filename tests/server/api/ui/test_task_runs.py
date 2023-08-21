from typing import Tuple, cast

import pendulum
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models
from prefect.server.api.ui.task_runs import TaskRunCount
from prefect.server.schemas import core, filters, states
from prefect.server.utilities.schemas import DateTimeTZ


class TestReadDashboardTaskRunCounts:
    @pytest.fixture
    def url(self) -> str:
        return "/ui/task_runs/dashboard/counts"

    @pytest.fixture
    def time_window(self) -> Tuple[DateTimeTZ, DateTimeTZ]:
        now = cast(DateTimeTZ, pendulum.datetime(2023, 6, 1, 18, tz="UTC"))
        return (now, now.subtract(hours=8))

    @pytest.fixture
    def task_run_filter(self, time_window) -> filters.TaskRunFilter:
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
        flow_run,
        time_window,
    ):
        now, eight_hours_ago = time_window
        runs_to_create = 100
        time_gap = (now - eight_hours_ago).as_timedelta() / runs_to_create

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
            url, json={"task_runs": task_run_filter.dict(json_compatible=True)}
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
            url, json={"task_runs": task_run_filter.dict(json_compatible=True)}
        )
        assert response.status_code == 200

        counts = [TaskRunCount(**count) for count in response.json()]
        assert counts == [
            TaskRunCount(completed=0, failed=0) for _ in range(len(counts))
        ]

    async def test_returns_completed_and_failed_counts(
        self,
        url: str,
        task_run_filter: filters.TaskRunFilter,
        client: AsyncClient,
        create_task_runs,
    ):
        response = await client.post(
            url, json={"task_runs": task_run_filter.dict(json_compatible=True)}
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
