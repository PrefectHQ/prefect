import pytest
from unittest.mock import MagicMock

import prefect
from prefect import Flow, task, Task
from prefect.core import Edge
from prefect.engine.state import Success, Failed, Skipped, Pending
from prefect.engine import signals
from prefect.tasks.core.resource_manager import (
    ResourceManager,
    resource_manager,
    resource_cleanup_trigger,
)


class MyResource:
    def __init__(self, on_setup=None, on_cleanup=None):
        self.on_setup = on_setup
        self.on_cleanup = on_cleanup

    def setup(self):
        return self.on_setup() if callable(self.on_setup) else self.on_setup

    def cleanup(self, val):
        if self.on_cleanup:
            self.on_cleanup(val)


@task
def inc(x):
    return x + 1


@task
def add(x, y):
    return x + y


def test_resource_manager_default_init():
    manager = resource_manager(MyResource)
    assert manager.name == "MyResource"
    assert manager.resource_class == MyResource
    assert manager.init_task_kwargs == {"name": "MyResource"}
    assert manager.setup_task_kwargs == {
        "name": "MyResource.setup",
        "checkpoint": False,
    }
    assert manager.cleanup_task_kwargs == {
        "name": "MyResource.cleanup",
        "trigger": resource_cleanup_trigger,
        "skip_on_upstream_skip": False,
        "checkpoint": False,
    }


def test_resource_manager_init_overrides():
    init_task_kwargs = {"name": "init_name", "tags": ["init"]}
    setup_task_kwargs = {"name": "setup_name", "tags": ["setup"], "checkpoint": True}
    cleanup_task_kwargs = {
        "name": "cleanup_name",
        "tags": ["cleanup"],
        "checkpoint": True,
    }

    manager = resource_manager(
        MyResource,
        name="Test",
        init_task_kwargs=init_task_kwargs,
        setup_task_kwargs=setup_task_kwargs,
        cleanup_task_kwargs=cleanup_task_kwargs,
    )
    assert manager.name == "Test"
    assert manager.resource_class == MyResource
    assert manager.init_task_kwargs == init_task_kwargs
    assert manager.setup_task_kwargs == setup_task_kwargs
    assert manager.cleanup_task_kwargs == {
        "trigger": resource_cleanup_trigger,
        "skip_on_upstream_skip": False,
        **cleanup_task_kwargs,
    }

    # Copies used
    assert manager.init_task_kwargs is not init_task_kwargs
    assert manager.setup_task_kwargs is not setup_task_kwargs
    assert manager.cleanup_task_kwargs is not cleanup_task_kwargs


def test_resource_manager_decorator_init():
    manager = resource_manager(name="Test")(ResourceManager)
    assert manager.name == "Test"
    assert manager.init_task_kwargs["name"] == "Test"
    assert manager.setup_task_kwargs["name"] == "Test.setup"
    assert manager.cleanup_task_kwargs["name"] == "Test.cleanup"
    assert manager.resource_class == ResourceManager


def test_resource_manager_sets_and_clears_context():
    manager = resource_manager(MyResource)

    with Flow("test"):
        m1 = manager(1)
        m2 = manager(2)
        assert "resource" not in prefect.context
        with m1:
            assert prefect.context["resource"] is m1
            with m2:
                assert prefect.context["resource"] is m2
            assert prefect.context["resource"] is m1
        assert "resource" not in prefect.context


def test_resource_manager_errors_no_flow_in_context():
    manager = resource_manager(MyResource)

    with pytest.raises(ValueError, match="Could not infer an active Flow"):
        with manager():
            pass


def test_resource_cannot_be_used_with_multiple_flows():
    flow = Flow("test")
    flow2 = Flow("test2")
    manager = resource_manager(MyResource)
    with pytest.raises(ValueError, match="Multiple flows"):
        with manager(flow=flow):
            inc(1, flow=flow2)


@pytest.mark.parametrize("api", ["functional", "imperative"])
def test_resource_manager_generated_flow_structure(api):
    manager = resource_manager(MyResource)

    if api == "functional":
        with Flow("test") as flow:
            a = inc(1)
            context = manager(a)
            with context as resource:
                b = add(resource, a)
                c = inc(b)
                d = inc(2)
                e = inc(d)
                f = inc(3)
            g = inc(f)
    else:
        flow = Flow("test")
        a = inc(1, flow=flow)
        context = manager(a, flow=flow)
        with context as resource:
            b = add(resource, a, flow=flow)
            c = inc(b, flow=flow)
            d = inc(2, flow=flow)
            e = inc(d, flow=flow)
            f = inc(3, flow=flow)
        g = inc(f, flow=flow)

    # task kwargs successfully forwarded to tasks
    assert context.init_task.name == "MyResource"
    assert context.setup_task.name == "MyResource.setup"
    assert context.cleanup_task.name == "MyResource.cleanup"
    assert not context.cleanup_task.skip_on_upstream_skip

    # Reference tasks setup properly
    assert flow.reference_tasks() == {c, e, g}

    # Check that:
    # - Tasks with no upstream dependency in the resource context have
    #   the setup task set as an upstream dependency
    # - Tasks with no downstream dependency in the resource context have
    #   the cleanup task set as a downstream dependency
    # - All other tasks only have explicit dependencies
    assert flow.upstream_tasks(a) == set()
    assert flow.upstream_tasks(context.init_task) == {a}
    assert flow.upstream_tasks(context.setup_task) == {context.init_task}
    assert flow.upstream_tasks(b) == {context.setup_task, a}
    assert flow.upstream_tasks(c) == {b}
    assert flow.upstream_tasks(d) == {context.setup_task}
    assert flow.upstream_tasks(e) == {d}
    assert flow.upstream_tasks(f) == {context.setup_task}
    assert flow.upstream_tasks(g) == {f}
    assert flow.upstream_tasks(context.cleanup_task) == {
        context.init_task,
        context.setup_task,
        c,
        e,
        f,
    }


def test_resource_manager_generated_flow_structure_no_setup():
    @resource_manager
    class MyResource:
        def __init__(self, a):
            self.a = a

        def cleanup(self, val):
            pass

    with Flow("test") as flow:
        a = inc(1)
        context = MyResource(a)
        with context as resource:
            b = add(resource, a)
            c = inc(b)
            d = inc(2)
            e = inc(d)
            f = inc(3)
        g = inc(f)

    # task kwargs successfully forwarded to tasks
    assert context.init_task.name == "MyResource"
    assert context.setup_task is None
    assert resource is None
    assert context.cleanup_task.name == "MyResource.cleanup"
    assert not context.cleanup_task.skip_on_upstream_skip

    # Reference tasks setup properly
    assert flow.reference_tasks() == {c, e, g}

    # Check that:
    # - Tasks with no downstream dependency in the resource context have
    #   the cleanup task set as a downstream dependency
    # - All other tasks only have explicit dependencies
    assert flow.upstream_tasks(a) == set()
    assert flow.upstream_tasks(context.init_task) == {a}
    assert flow.upstream_tasks(b) == {a}
    assert flow.upstream_tasks(c) == {b}
    assert flow.upstream_tasks(d) == set()
    assert flow.upstream_tasks(e) == {d}
    assert flow.upstream_tasks(f) == set()
    assert flow.upstream_tasks(g) == {f}
    assert flow.upstream_tasks(context.cleanup_task) == {
        context.init_task,
        c,
        e,
        f,
    }


def test_resource_manager_execution_success():
    on_setup = MagicMock(return_value=100)
    on_cleanup = MagicMock()

    manager = resource_manager(MyResource)

    with Flow("test") as flow:
        context = manager(on_setup=on_setup, on_cleanup=on_cleanup)
        with context as resource:
            a = inc(resource)
            inc(a)

    state = flow.run()
    assert on_setup.called
    assert on_cleanup.call_args == ((100,), {})
    assert state.is_successful()
    for r in state.result.values():
        assert r.is_successful()


def test_resource_manager_execution_success_no_setup():
    @resource_manager
    class MyResource:
        def __init__(self, on_cleanup):
            self.on_cleanup = on_cleanup

        def cleanup(self, val):
            self.on_cleanup(val)

    on_cleanup = MagicMock()

    with Flow("test") as flow:
        context = MyResource(on_cleanup)
        with context:
            inc(inc(1))

    state = flow.run()
    assert on_cleanup.call_args == ((None,), {})
    assert state.is_successful()
    for r in state.result.values():
        assert r.is_successful()


@pytest.mark.parametrize("kind", ["init", "setup", "cleanup"])
def test_resource_manager_execution_with_failure_in_manager(kind):
    on_setup = MagicMock(return_value=100)
    on_cleanup = MagicMock()

    def raise_if(val):
        if kind == val:
            raise ValueError("Oh No!")

    @resource_manager
    class Resource:
        def __init__(self):
            raise_if("init")

        def setup(self):
            out = on_setup()
            raise_if("setup")
            return out

        def cleanup(self, val):
            on_cleanup(val)
            raise_if("cleanup")

    with Flow("test") as flow:
        context = Resource()
        with context as resource:
            a = inc(resource)

    state = flow.run()

    if kind == "init":
        assert state.is_failed()
        assert state.result[context.init_task].is_failed()
        assert state.result[context.setup_task].is_failed()
        assert state.result[context.cleanup_task].is_skipped()
        assert state.result[a].is_failed()
        assert not on_setup.called
        assert not on_cleanup.called
    elif kind == "setup":
        assert state.is_failed()
        assert state.result[context.init_task].is_successful()
        assert state.result[context.setup_task].is_failed()
        assert state.result[context.cleanup_task].is_skipped()
        assert state.result[a].is_failed()
        assert on_setup.called
        assert not on_cleanup.called
    else:
        assert state.is_successful()
        assert state.result[context.init_task].is_successful()
        assert state.result[context.setup_task].is_successful()
        assert state.result[context.cleanup_task].is_failed()
        assert state.result[a].is_successful()
        assert on_setup.called
        assert on_cleanup.call_args == ((100,), {})


def test_resource_tasks_always_rerun_on_flow_restart():
    @resource_manager
    class Resource:
        def __init__(self):
            nonlocal init_run
            init_run = True

        def setup(self):
            nonlocal setup_run
            setup_run = True
            return 1

        def cleanup(self, val):
            nonlocal cleanup_run
            cleanup_run = True

    with Flow("test") as flow:
        context = Resource()
        with context as resource:
            a = inc(resource)
            b = inc(resource)
            c = add(a, b)

    # rerun from partial completion
    task_states = {
        context.init_task: Success(result=Resource.resource_class()),
        context.setup_task: Success(),
        context.cleanup_task: Success(),
        a: Success(result=2),
    }
    init_run = setup_run = cleanup_run = False
    res = flow.run(task_states=task_states)
    assert res.is_successful()
    assert res.result[a].result == 2
    assert res.result[b].result == 2
    assert res.result[c].result == 4
    assert not init_run  # existing result used
    assert setup_run  # setup re-run
    assert cleanup_run  # cleanup re-run


def test_resource_cleanup_trigger():
    def generate(init, setup, task):
        return {
            Edge(Task(), Task(), key="mgr"): init,
            Edge(Task(), Task(), key="resource"): setup,
            Edge(Task(), Task()): task,
        }

    assert resource_cleanup_trigger(generate(Success(), Success(), Success()))
    assert resource_cleanup_trigger(generate(Success(), Success(), Failed()))
    assert resource_cleanup_trigger(generate(Success(), Success(), Skipped()))

    # Not all finished
    with pytest.raises(signals.TRIGGERFAIL):
        resource_cleanup_trigger(generate(Success(), Success(), Pending()))

    with pytest.raises(signals.SKIP, match="init failed"):
        resource_cleanup_trigger(generate(Failed(), Success(), Success()))

    with pytest.raises(signals.SKIP, match="init skipped"):
        resource_cleanup_trigger(generate(Skipped(), Success(), Success()))

    with pytest.raises(signals.SKIP, match="setup failed"):
        resource_cleanup_trigger(generate(Success(), Failed(), Success()))

    with pytest.raises(signals.SKIP, match="setup skipped"):
        resource_cleanup_trigger(generate(Success(), Skipped(), Success()))


@task
def post_cleanup():
    pass


def test_resource_cleanup_reference_tasks():
    manager = resource_manager(MyResource)

    with Flow("test") as flow:
        with manager() as resource:
            a = inc(resource)
            b = inc(a)
            c = inc(2)
        d = inc(b)

    assert flow.reference_tasks() == {c, d}

    with Flow("test") as flow:
        context = manager()
        with context as resource:
            a = inc(resource)
            b = inc(a)
            c = inc(2)
        d = inc(b)
        e = post_cleanup(upstream_tasks=[context.cleanup_task])

    assert flow.reference_tasks() == {c, d, e}
