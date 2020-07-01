import inspect
from unittest.mock import MagicMock
import pytest

import cloudpickle
from multiprocessing.pool import ThreadPool

import prefect
from prefect.tasks.resources.base import (
    ResourceHandle,
    ResourcePool,
    Resource,
    resource,
)
from prefect.utilities.logging import get_logger


class Unpickleable:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __reduce__(self):
        raise ValueError("Don't even think about pickling me")


class TestResourceHandle:
    def test_resource_handle_with_return(self):
        handle = ResourceHandle(lambda x, y: Unpickleable(x, y), ("xx",), {"y": "yy"})

        res = handle.get()
        assert res.x == "xx"
        assert res.y == "yy"
        assert handle.get() is res

        handle.clear()
        assert handle.func is None
        assert handle.args is None
        assert handle.kwargs is None

        with pytest.raises(ValueError, match="Cannot access value of `Resource`"):
            handle.get()

    def test_resource_handle_with_yield(self):
        cleanup = MagicMock()

        def func(x, y):
            yield Unpickleable(x, y)
            cleanup()

        handle = ResourceHandle(func, ("xx",), {"y": "yy"})

        res = handle.get()
        assert res.x == "xx"
        assert res.y == "yy"
        assert not cleanup.called

        assert handle.get() is res

        handle.clear()
        assert handle.func is None
        assert handle.args is None
        assert handle.kwargs is None
        assert cleanup.called

        with pytest.raises(ValueError, match="Cannot access value of `Resource`"):
            handle.get()

    def test_resource_handle_pickle(self):
        logger = get_logger()
        handle = ResourceHandle(
            Unpickleable, ("xx",), {"y": "yy"}, name="task name", logger=logger
        )
        res = handle.get()
        assert isinstance(res, Unpickleable)

        # Can pickle, even if resource isn't pickleable
        s = cloudpickle.dumps(handle)

        assert cloudpickle.loads(s) is handle
        del handle

        handle1 = cloudpickle.loads(s)
        assert handle1.func == Unpickleable
        assert handle1.args == ("xx",)
        assert handle1.kwargs == {"y": "yy"}
        assert handle1.name == "task name"
        assert handle1.logger is logger
        res == handle1.get()
        assert isinstance(res, Unpickleable)

        # unpickling multiple times always results in same instance
        handle2 = cloudpickle.loads(s)
        assert handle1 is handle2

        # resource cache isn't thread local
        with ThreadPool(1) as pool:
            handle3 = pool.apply(cloudpickle.loads, (s,))
        assert handle3 is handle1

    def test_resource_handle_destructor(self):
        del_method = MagicMock()
        cleanup = MagicMock()

        class MyClass:
            def __del__(self):
                del_method()

        def func():
            yield MyClass()
            cleanup()

        handle = ResourceHandle(func)
        assert isinstance(handle.get(), MyClass)
        assert not del_method.called
        del handle
        assert del_method.called
        assert cleanup.called

    def test_errors_in_resource_cleanup_are_logged(self):
        logger = MagicMock()

        def func():
            yield "hello"
            raise ValueError("OH NO!")

        handle = ResourceHandle(func, logger=logger, name="task name")
        handle.get()
        handle.clear()
        assert logger.warning.called
        assert logger.warning.call_args[0][1] == "task name"
        assert isinstance(logger.warning.call_args[1]["exc_info"], ValueError)
        assert handle.func is None


class TestResourcePool:
    def test_resource_pool_clears_resources(self):
        with ResourcePool() as pool:
            handle = ResourceHandle(lambda: 1)
            assert handle in pool.resources
            assert handle.get() == 1
        assert handle.func is None
        with pytest.raises(ValueError, match="Cannot access value of `Resource`"):
            handle.get()

    def test_resource_pool_clears_resources_that_were_unpickled(self):
        s = cloudpickle.dumps(ResourceHandle(lambda: 1))
        with ResourcePool() as pool:
            handle = cloudpickle.loads(s)
            assert handle in pool.resources
            assert handle.get() == 1
        assert handle.func is None
        with pytest.raises(ValueError, match="Cannot access value of `Resource`"):
            handle.get()


class TestResource:
    def test_resource_task_name(self):
        def myresource(x, y=1):
            return x + y

        r = Resource(myresource)
        assert r.name == "myresource"

        r = Resource(myresource, name="task name")
        assert r.name == "task name"

    def test_resource_decorator(self):
        @resource
        def myresource(x, y=1):
            return x + y

        assert isinstance(myresource, Resource)
        assert myresource.name == "myresource"

        @resource(name="task name")
        def myresource(x, y=1):
            return x + y

        assert isinstance(myresource, Resource)
        assert myresource.name == "task name"

    def test_resource_task_run_signature(self):
        @resource
        def myresource(x, y=1):
            return x + y

        sig = inspect.Signature.from_callable(myresource.run)
        assert sig.return_annotation == ResourceHandle
        assert set(sig.parameters.keys()) == {"x", "y"}

    def test_resource_task_run(self):
        logger = MagicMock()

        @resource
        def myresource(x, y=1):
            return x + y

        with prefect.context(task_full_name="task name", logger=logger):
            handle = myresource.run(1, y=2)
            assert isinstance(handle, ResourceHandle)
            assert handle.args == (1,)
            assert handle.kwargs == {"y": 2}
            assert handle.logger is logger
            assert handle.name == "task name"
            assert handle.get() == 3
