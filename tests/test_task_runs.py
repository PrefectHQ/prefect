from prefect.task_runs import TaskRunWaiter


class TestTaskRunWaiter:
    def test_instance_returns_singleton(self):
        assert TaskRunWaiter.instance() is TaskRunWaiter.instance()
