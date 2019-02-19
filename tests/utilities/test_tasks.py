import pytest

from prefect.core import Flow, Task
from prefect.engine.signals import PAUSE
from prefect.engine.state import Paused, Resume
from prefect.utilities import tasks


class TestTaskDecorator:
    def test_task_decorator_can_be_used_without_calling(self):
        @tasks.task
        def fun(x, y):
            return x + y

    def test_task_decorator_generates_new_tasks_upon_subsequent_calls(self):
        @tasks.task
        def fun(x, y):
            return x + y

        with Flow():
            res1 = fun(1, 2)
            res2 = fun(1, 2)
        assert isinstance(res1, Task)
        assert isinstance(res2, Task)
        assert res1 is not res2

    def test_task_decorator_with_args_must_be_called_in_flow_context(self):
        @tasks.task
        def fn(x):
            return x

        with pytest.raises(ValueError) as exc:
            fn(1)
        assert "Could not infer an active Flow context" in str(exc.value)

    def test_task_decorator_with_no_args_must_be_called_inside_flow_context(self):
        @tasks.task
        def fn():
            return 1

        with pytest.raises(ValueError):
            fn()

        with Flow():
            assert isinstance(fn(), Task)

    def test_task_decorator_with_default_args_must_be_called_inside_flow_context(self):
        @tasks.task
        def fn(x=1):
            return x

        with pytest.raises(ValueError):
            fn()

        with Flow():
            assert isinstance(fn(), Task)

    def test_task_decorator_with_required_args_must_be_called_with_args(self):
        @tasks.task
        def fn(x):
            return x

        with Flow():
            with pytest.raises(TypeError):
                fn()

    def test_task_decorator_returns_task_instance(self):
        @tasks.task
        def fn(x):
            return x

        assert isinstance(fn, Task)

    def test_task_decorator_validates_run_signature_against_varargs(self):
        with pytest.raises(ValueError):

            @tasks.task
            def fn(*args):
                pass

    def test_task_decorator_validates_run_signature_against_upstream_tasks_kwarg(self):
        with pytest.raises(ValueError):

            @tasks.task
            def fn(upstream_tasks):
                pass


def test_tag_contextmanager_works_with_task_decorator():
    @tasks.task
    def mytask():
        pass

    @tasks.task(tags=["default"])
    def tagged_task():
        pass

    with Flow():
        with tasks.tags("chris"):
            res = mytask()
            other = tagged_task()

    assert res.tags == {"chris"}
    assert other.tags == {"chris", "default"}


def test_copying_then_setting_tags_doesnt_leak_backwards():
    with Flow():
        t1 = Task()
        with tasks.tags("init-tag"):
            t2 = t1.copy()

    assert t2.tags == {"init-tag"}
    assert t1.tags == set()


def test_setting_tags_then_calling_copies_tags():
    with tasks.tags("init-tag"):
        t1 = Task()

    with Flow():
        t2 = t1()

    assert t2.tags == {"init-tag"}


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
            assert t3.tags == set(["1", "2", "3", "4", "5"])


class TestUnmappedContainer:
    def test_unmapped_initializes_with_task(self):
        t1 = Task()
        unmapped_t1 = tasks.unmapped(t1)
        assert unmapped_t1.task is t1

    def test_unmapped_converts_its_argument_to_task(self):
        unmapped_t1 = tasks.unmapped(5)
        assert isinstance(unmapped_t1.task, Task)

    def test_as_task_unpacks_unmapped_objects(self):
        t1 = Task()
        unmapped_t1 = tasks.unmapped(t1)
        assert tasks.as_task(t1) is t1


class TestPauseTask:
    def test_pause_task_pauses(self):
        class AddTask(Task):
            def run(self, x, y):
                if x == y:
                    tasks.pause_task("test message")
                return x + y

        with Flow() as f:
            t1 = AddTask()(1, 1)
        res = f.run(return_tasks=f.tasks)
        assert isinstance(res.result[t1], Paused)
        assert res.result[t1].message == "test message"

    def test_pause_task_doesnt_pause_sometimes(self):
        class OneTask(Task):
            def run(self):
                tasks.pause_task()
                return 1

        class AddTask(Task):
            def run(self, x, y):
                if x == y:
                    tasks.pause_task()
                return x + y

        with Flow() as f:
            t1 = AddTask()(1, 1)
            t2 = OneTask()(upstream_tasks=[t1])

        res = f.run(return_tasks=f.tasks, task_states={t1: Resume()})
        assert res.result[t1].is_successful()
        assert isinstance(res.result[t2], Paused)


class TestDefaultFromAttrs:
    @pytest.fixture
    def xtask(self):
        class A(Task):
            def __init__(self, x=None):
                self.x = x
                super().__init__()

            @tasks.defaults_from_attrs(["x"])
            def run(self, x=None):
                "Lil doc"
                return x

        return A

    @pytest.fixture
    def multitask(self):
        class B(Task):
            def __init__(self, x=None, y=None):
                self.x = x
                self.y = y
                super().__init__()

            @tasks.defaults_from_attrs(["x"])
            def run(self, x=None, y=None):
                return x, y

        return B

    def test_pulls_from_attr_if_not_provided_at_runtime(self, xtask):
        a = xtask(5)
        assert a.run() == 5

    def test_runtime_takes_precedence(self, xtask):
        a = xtask(5)
        assert a.run(x=6) == 6

    def test_even_none_at_runtime_takes_precedence(self, xtask):
        """
        This test ensures that `None` isn't some ambiguous special case: keywords
        provided at runtime _always_ take precedence.
        """
        a = xtask(5)
        assert a.run(x=None) is None

    def test_doc_is_unaffected(self, xtask):
        assert xtask.run.__doc__ == "Lil doc"

    def test_args_not_listed_are_unaffected(self, multitask):
        b = multitask(x=1, y=2)
        assert b.run() == (1, None)

    def test_works_with_multiple_args(self, multitask):
        b = multitask(x=1, y=2)
        assert b.run(y=3, x=55) == (55, 3)

    def test_raises_if_attr_wasnt_set_at_init(self):
        """
        It would be nice to raise this at creation time, but unfortunately
        the information just isn't available.
        """

        class Forgot(Task):
            @tasks.defaults_from_attrs(["x"])
            def run(self, x=None):
                return x

        t = Forgot()
        with pytest.raises(AttributeError) as exc:
            t.run()

        assert "no attribute 'x'" in str(exc.value)
