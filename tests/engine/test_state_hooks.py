from functools import partial

from prefect.utilities.callables import partial_with_name


class TestStateHooks:
    def test_hook_with_extra_default_arg(self):
        from prefect import flow

        def hook(flow, flow_run, state, foo=42):
            assert hook.__name__ == "hook"
            assert state.is_completed()
            assert foo == 42

        @flow(on_completion=[hook])
        def foo_flow():
            pass

        foo_flow()

    def test_hook_with_bound_kwargs(self):
        from prefect import flow

        def hook(flow, flow_run, state, **kwargs):
            assert hook.__name__ == "hook"
            assert state.is_completed()
            assert kwargs["foo"] == 42

        hook_with_kwargs = partial(hook, foo=42)
        hook_with_kwargs.__name__ = hook.__name__

        @flow(on_completion=[hook_with_kwargs])
        def foo_flow():
            pass

        foo_flow()

    def test_hook_with_bound_kwargs_via_utility(self):
        from prefect import flow

        def hook(flow, flow_run, state, **kwargs):
            assert hook.__name__ == "hook"
            assert state.is_completed()
            assert kwargs["foo"] == 42
            assert kwargs["bar"] == 99

        @flow(on_completion=[partial_with_name(hook, **{"foo": 42, "bar": 99})])
        def foo_flow():
            pass

        foo_flow()
