import copy
import datetime

import pytest

import prefect
from prefect.flow import Flow, TaskResult
from prefect.task import Task
from prefect.utilities.tasks import task


class AddTask(Task):

    def run(self, x, y=1):
        return x + y


class TestBasicTask:
    def test_create_task(self):
        t1 = Task()
        t2 = Task()

        assert t1.id != t2.id
        assert t1.name == t2.name


    def test_task_inputs(self):

        t = AddTask()
        assert t.inputs() == ('x', 'y')

class TestTasksInFlows:

    def test_create_task_in_context(self):
        t1 = Task()
        with Flow() as f:
            t2 = Task()

        assert t1 not in f.tasks
        assert t2 in f.tasks

    def test_call_task(self):
        t1 = Task()
        t2 = Task()
        add = AddTask()

        # combining three tasks creates a flow
        with Flow():
            result_1 = add(t1, t2)
        assert isinstance(result_1, TaskResult)
        assert result_1.flow.tasks == set([t1, t2, add])


class TestTaskFactory:
    def test_task_factory_decorator(self):
        @task()
        def add(x, y=1):
            return x + y

        assert isinstance(add(1, 2), TaskResult)
