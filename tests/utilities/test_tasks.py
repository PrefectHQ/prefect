from prefect.core import Flow, Task
from prefect.utilities import tasks


def test_task_decorator_can_be_used_without_calling():
    @tasks.task
    def fun(x, y):
        return x + y


def test_task_decorator_generates_new_tasks_upon_subsequent_calls():
    @tasks.task
    def fun(x, y):
        return x + y

    with Flow():
        res1 = fun(1, 2)
        res2 = fun(1, 2)
    assert isinstance(res1, Task)
    assert res1 is not res2


def test_context_manager_for_setting_group():
    """
    Test setting a Task group with a context manager, including:
        - top level
        - nested
        - nested with explicit group passed
        - nested with append
        - top level with append
    """
    with tasks.group("1"):
        t1 = Task()
        assert t1.group == "1"

        with tasks.group("2"):
            t2 = Task()
            assert t2.group == "2"

            t3 = Task(group="3")
            assert t3.group == "3"

        with tasks.group("2", append=True):
            t4 = Task()
            assert t4.group == "1/2"

    with tasks.group("1", append=True):
        t5 = Task()
        assert t5.group == "1"


def test_context_manager_for_setting_tags():
    """
    Test setting Task tags with a context manager, including:
        - top level
        - nested
        - nested with explicit tags
    """

    with tasks.tags("1", "2"):
        t1 = Task()
        assert t1.tags == set(["1", "2"])

        with tasks.tags("3", "4"):
            t2 = Task()
            assert t2.tags == set(["1", "2", "3", "4"])

            t3 = Task(tags=["5"])
            assert t3.tags == set(["5"])
