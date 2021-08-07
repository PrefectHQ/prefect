import asyncio
from uuid import uuid4
import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas.states import State, StateType
from prefect.orion.models import orm

N_FLOWS = 10
N_FLOW_RUNS = 10
N_TASK_RUNS = 250


def batches(lst, n):
    """Yield successive n-sized batches from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


@pytest.fixture
async def fill_db(database_session):

    flows = [schemas.core.Flow(id=uuid4(), name=str(i)) for i in range(N_FLOWS)]
    flow_runs = [
        schemas.core.FlowRun(id=uuid4(), flow_id=f.id)
        for f in flows
        for _ in range(N_FLOW_RUNS)
    ]
    task_runs = [
        schemas.core.TaskRun(
            id=uuid4(), task_key=str(i % 5), dynamic_key=str(i), flow_run_id=r.id
        )
        for r in flow_runs
        for i in range(N_TASK_RUNS)
    ]

    flow_run_states = []
    task_run_states = []

    for i, flow_run in enumerate(flow_runs):
        if i % 3 == 0:
            flow_run_states.extend(
                [
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().subtract(seconds=10)
                            ),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.PENDING,
                            timestamp=pendulum.now().subtract(seconds=10),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            timestamp=pendulum.now().subtract(seconds=9),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.COMPLETED,
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                ]
            )
        elif i % 3 == 1:
            flow_run_states.extend(
                [
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().subtract(seconds=10)
                            ),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.PENDING,
                            timestamp=pendulum.now().subtract(seconds=10),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            timestamp=pendulum.now().subtract(seconds=9),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            name="AwaitingRetry",
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            name="Retrying",
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.FAILED,
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                ]
            )
        elif i % 3 == 2:
            flow_run_states.extend(
                [
                    dict(
                        flow_run_id=flow_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().add(seconds=i)
                            ),
                        ).dict(exclude_none=True),
                    )
                ]
            )

    for i, task_run in enumerate(task_runs):
        if i % 3 == 0:
            task_run_states.extend(
                [
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().subtract(seconds=10)
                            ),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.PENDING,
                            timestamp=pendulum.now().subtract(seconds=10),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            timestamp=pendulum.now().subtract(seconds=9),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.COMPLETED,
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                ]
            )
        elif i % 3 == 1:
            task_run_states.extend(
                [
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().subtract(seconds=10)
                            ),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.PENDING,
                            timestamp=pendulum.now().subtract(seconds=10),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            timestamp=pendulum.now().subtract(seconds=9),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            name="AwaitingRetry",
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.RUNNING,
                            name="Retrying",
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.FAILED,
                            timestamp=pendulum.now().subtract(seconds=8),
                        ).dict(exclude_none=True),
                    ),
                ]
            )
        elif i % 3 == 2:
            task_run_states.extend(
                [
                    dict(
                        task_run_id=task_run.id,
                        **State(
                            id=uuid4(),
                            type=StateType.SCHEDULED,
                            timestamp=pendulum.now().subtract(seconds=20),
                            state_details=dict(
                                scheduled_time=pendulum.now().add(seconds=i)
                            ),
                        ).dict(exclude_none=True),
                    )
                ]
            )

    tasks = []
    async with database_session.begin():
        tasks.append(
            asyncio.create_task(
                database_session.execute(
                    sa.insert(orm.Flow.__table__).values(
                        [o.dict(exclude_unset=True) for o in flows]
                    )
                )
            )
        )

        for i, batch in enumerate(batches(flow_runs, 1000)):
            print(f"batch {i} of flow runs")
            tasks.append(
                asyncio.create_task(
                    database_session.execute(
                        sa.insert(orm.FlowRun.__table__).values(
                            [o.dict(exclude_unset=True) for o in batch]
                        )
                    )
                )
            )

        for i, batch in enumerate(batches(flow_run_states, 1000)):
            print(f"batch {i} of flow run states")
            tasks.append(
                asyncio.create_task(
                    database_session.execute(
                        sa.insert(orm.FlowRunState.__table__).values(batch)
                    )
                )
            )
        for i, batch in enumerate(batches(task_runs, 1000)):
            print(f"batch {i} of task runs")
            tasks.append(
                asyncio.create_task(
                    database_session.execute(
                        sa.insert(orm.TaskRun.__table__).values(
                            [o.dict(exclude_unset=True) for o in batch]
                        )
                    )
                )
            )

        for i, batch in enumerate(batches(task_run_states, 1000)):
            print(f"batch {i} of task run states")
            tasks.append(
                asyncio.create_task(
                    database_session.execute(
                        sa.insert(orm.TaskRunState.__table__).values(batch)
                    )
                )
            )

        await asyncio.gather(*tasks)
