from prefect.utilities.tasks import task
from prefect.core import Flow, Task


def test_task_decorator_can_be_used_without_calling():
    @task
    def fun(x, y):
        return x + y


def test_task_decorator_generates_new_tasks_upon_subsequent_calls():
    @task
    def fun(x, y):
        return x + y

    with Flow():
        res1 = fun(1, 2)
        res2 = fun(1, 2)
    assert isinstance(res1, Task)
    assert res1 is not res2
