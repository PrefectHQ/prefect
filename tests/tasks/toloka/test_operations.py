import pandas as pd
import prefect
import pytest
import pytz
from freezegun import freeze_time
from functools import partial
from datetime import datetime, timedelta
from prefect.tasks.toloka.operations import (
    create_exam_pool,
    create_pool,
    create_project,
    create_tasks,
    get_assignments,
    get_assignments_df,
    open_exam_pool,
    open_pool,
    wait_pool,
)
from prefect.tasks.toloka.utils import DEFAULT_TOLOKA_SECRET_NAME, structure_from_conf
from toloka.client import Assignment, Pool, Project, TolokaClient, Training
from toloka.client import Task as TolokaTask
from toloka.client.assignment import GetAssignmentsTsvParameters
from toloka.client.batch_create_results import TaskBatchCreateResult
from toloka.client.quality_control import QualityControl
from unittest.mock import Mock, patch


@pytest.fixture
def secrets_mock():
    with prefect.context(secrets={DEFAULT_TOLOKA_SECRET_NAME: 'some-token'}):
        yield


PROJECT_ID = 'some-project-id'
POOL_ID = 'some-pool-id'
TRAINING_ID = 'some-training-id'


@pytest.fixture
def project_mock():
    return Project(id=PROJECT_ID)


@pytest.fixture
def pool_mock():
    return Pool(id=POOL_ID)


@pytest.fixture
def training_mock():
    return Training(id=TRAINING_ID)


@pytest.fixture
def tasks_mock():
    return [TolokaTask(input_values={}, id=str(index)) for index in range(3)]


@pytest.fixture
def tasks_creation_result(tasks_mock):
    return TaskBatchCreateResult(items=tasks_mock)


@pytest.fixture
def assignments_mock():
    return [Assignment(id=f'assignment-{index}') for index in range(3)]


@pytest.fixture
def assignments_df_mock():
    return pd.DataFrame.from_records([{'ASSIGNMENT:assignment_id': f'assignment-{index}'}
                                      for index in range(3)])


@pytest.fixture
def toloka_client_mock(
    secrets_mock,
    pool_mock,
    training_mock,
    tasks_creation_result,
    assignments_mock,
    assignments_df_mock,
):
    client = Mock()
    client.create_project = partial(structure_from_conf, cl=Project)
    client.create_pool = partial(structure_from_conf, cl=Pool)
    client.create_training = partial(structure_from_conf, cl=Training)
    client.create_tasks = Mock(return_value=tasks_creation_result)
    client.open_pool = Mock(return_value=pool_mock)
    client.open_training = Mock(return_value=training_mock)
    client.get_assignments = Mock(return_value=iter(assignments_mock))
    client.get_assignments_df = Mock(return_value=assignments_df_mock)
    with patch('prefect.tasks.toloka.utils.TolokaClient', Mock(return_value=client)):
        yield client


def test_create_project(toloka_client_mock, project_mock):
    assert project_mock == create_project.run(project_mock.unstructure())


class TestCreateExamPool:
    def test_create_exam_pool(self, toloka_client_mock, training_mock):
        res = create_exam_pool.run(training_mock.unstructure())
        assert training_mock == res

    def test_create_exam_pool_with_project(self, toloka_client_mock, training_mock, project_mock):
        res = create_exam_pool.run(training_mock.unstructure(), project_id=project_mock)
        assert project_mock.id == res.project_id
        res.project_id = None
        assert training_mock == res


class TestCreatePool:
    def test_create_pool(self, toloka_client_mock, pool_mock):
        res = create_pool.run(pool_mock.unstructure())
        assert pool_mock == res

    def test_create_pool_with_project(self, toloka_client_mock, pool_mock, project_mock):
        res = create_pool.run(pool_mock.unstructure(), project_id=project_mock)
        assert project_mock.id == res.project_id
        res.project_id = None
        assert pool_mock == res

    def test_create_pool_with_exam(self, toloka_client_mock, pool_mock, project_mock, training_mock):
        training_requirement = QualityControl.TrainingRequirement(training_passing_skill_value=90)
        pool_mock.quality_control = QualityControl(training_requirement=training_requirement)
        res = create_pool.run(pool_mock.unstructure(), project_id=project_mock, exam_pool_id=training_mock)
        assert training_mock.id == res.quality_control.training_requirement.training_pool_id
        res.quality_control.training_requirement.training_pool_id = None
        res.project_id = None
        assert pool_mock == res

    def test_create_pool_with_exam_error(self, toloka_client_mock, pool_mock, project_mock, training_mock):
        pool_mock.quality_control = QualityControl()
        with pytest.raises(ValueError, match='pool.quality_control.training_requirement'):
            create_pool.run(pool_mock.unstructure(), project_id=project_mock, exam_pool_id=training_mock)

    def test_create_pool_with_expiration_exact(self, toloka_client_mock, pool_mock):
        dt = datetime(2022, 1, 1, tzinfo=pytz.UTC)
        res = create_pool.run(pool_mock.unstructure(), expiration=dt)
        assert dt == res.will_expire

    def test_create_pool_with_expiration_relative(self, toloka_client_mock, pool_mock):
        with freeze_time(datetime(2022, 1, 1, tzinfo=pytz.UTC)):
            res = create_pool.run(pool_mock.unstructure(), expiration=timedelta(days=31))
        assert datetime(2022, 2, 1, tzinfo=pytz.UTC) == res.will_expire.replace(tzinfo=pytz.UTC)

    def test_create_pool_with_reward(self, toloka_client_mock, pool_mock):
        reward = 0.05
        res = create_pool.run(pool_mock.unstructure(), reward_per_assignment=reward)
        assert reward == res.reward_per_assignment
        res.reward_per_assignment = None
        assert pool_mock == res


class TestCreateTasks:
    def test_create_tasks(self, toloka_client_mock, tasks_mock, tasks_creation_result):
        kwargs = {'allow_defaults': True, 'open_pool': True, 'skip_invalid_items': False}
        assert tasks_creation_result == create_tasks.run(
            [task.unstructure() for task in tasks_mock],
            **kwargs
        )
        toloka_client_mock.create_tasks.assert_called()
        call = toloka_client_mock.create_tasks.mock_calls[0]
        assert (tasks_mock,) == call[1], call[1]
        assert kwargs == call[2], call[2]

    def test_create_tasks_with_pool(self, toloka_client_mock, tasks_mock, tasks_creation_result, pool_mock):
        assert tasks_creation_result == create_tasks.run(
            [task.unstructure() for task in tasks_mock],
            pool_id=pool_mock,
        )
        call = toloka_client_mock.create_tasks.mock_calls[0]
        assert all(task.pool_id == pool_mock.id for task in call[1][0])

    def test_create_tasks_with_exam_pool(self, toloka_client_mock, tasks_mock, tasks_creation_result, training_mock):
        assert tasks_creation_result == create_tasks.run(
            [task.unstructure() for task in tasks_mock],
            pool_id=training_mock,
        )
        call = toloka_client_mock.create_tasks.mock_calls[0]
        assert all(task.pool_id == training_mock.id for task in call[1][0])


class TestOpenPool:
    def test_open_pool(self, toloka_client_mock, pool_mock):
        assert pool_mock == open_pool.run(pool_mock)

    def test_open_pool_by_id(self, toloka_client_mock, pool_mock):
        assert pool_mock == open_pool.run(pool_mock.id)


class TestOpenExamPool:
    def test_open_exam_pool(self, toloka_client_mock, training_mock):
        assert training_mock == open_exam_pool.run(training_mock)

    def test_open_exam_pool_by_id(self, toloka_client_mock, training_mock):
        assert training_mock == open_exam_pool.run(training_mock.id)


class TestGetAssignments:
    def test_get_assignments_by_pool_object(self, toloka_client_mock, pool_mock, assignments_mock):
        assert assignments_mock == get_assignments.run(pool_mock)
        assert pool_mock.id == toloka_client_mock.get_assignments.mock_calls[0][2]['pool_id']

    def test_get_assignments_by_pool_id(self, toloka_client_mock, pool_mock, assignments_mock):
        assert assignments_mock == get_assignments.run(pool_mock.id)

    def test_get_assignments_with_status(self, toloka_client_mock, pool_mock, assignments_mock):
        assert assignments_mock == get_assignments.run(pool_mock.id, ['ACCEPTED'])
        assert ['ACCEPTED'] == toloka_client_mock.get_assignments.mock_calls[0][2]['status']


class TestGetAssignmentsDf:
    def test_get_assignments_df_by_pool_object(self, toloka_client_mock, pool_mock, assignments_df_mock):
        assert assignments_df_mock.equals(get_assignments_df.run(pool_mock))
        assert pool_mock.id == toloka_client_mock.get_assignments_df.mock_calls[0][2]['pool_id']
        assert [] == toloka_client_mock.get_assignments_df.mock_calls[0][2]['status']
        assert 'field' not in toloka_client_mock.get_assignments_df.mock_calls[0][2]

    def test_get_assignments_df_by_pool_id(self, toloka_client_mock, pool_mock, assignments_df_mock):
        assert assignments_df_mock.equals(get_assignments_df.run(pool_mock.id))

    def test_get_assignments_df_with_status(self, toloka_client_mock, pool_mock, assignments_df_mock):
        assert assignments_df_mock.equals(get_assignments_df.run(pool_mock.id, 'APPROVED'))
        assert ['APPROVED'] == toloka_client_mock.get_assignments_df.mock_calls[0][2]['status']

    def test_get_assignments_df_with_kwargs(self, toloka_client_mock, pool_mock, assignments_df_mock):
        kwargs = {'status': ['APPROVED'],
                  'start_time_from': datetime(2022, 1, 1),
                  'start_time_to': datetime(2022, 2, 1),
                  'exclude_banned': True,
                  'field': GetAssignmentsTsvParameters.Field.ASSIGNMENT_ID}
        assert assignments_df_mock.equals(get_assignments_df.run(pool_mock.id, **kwargs))
        assert {'pool_id': pool_mock.id, **kwargs} == toloka_client_mock.get_assignments_df.mock_calls[0][2]
