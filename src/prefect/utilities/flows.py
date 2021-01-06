import inspect
import sys
from functools import wraps
from typing import Callable, Union, Dict, Any

from toolz import curry

import prefect

# A reusable type definition for flows or a function that creates a flow
ResolvesToFlow = Union[prefect.Flow, Callable[[], prefect.Flow]]


@curry
def flow_builder(
    fn: Callable[..., None],
    run_kwargs: dict = None,
    register_kwargs: dict = None,
    **flow_kwargs,
) -> Callable[..., prefect.Flow]:
    """
    Wraps a function with a Prefect Flow context and calls `run_or_register` so the
    flow file can be run as a script. The function *must* take `flow` as the first
    argument. The flow name defaults to the name of the function with '_' replaced with
    '-'.

    Args:
        fn: The callable to wrap
        run_kwargs: A dict of kwargs to pass to `run_or_register` for script run calls
        register_kwargs: A dict of kwargs to pass to `run_or_register` for script
            register calls
        **flow_kwargs: Additional kwargs as passed to the `Flow` initializer

    Returns:
        A wrapped function with the flow context.

    Examples:

        Tasks called from within the function are added to the flow
        ```python
        from prefect import task
        from prefect.utilities.flows import flow_builder

        @task(log_stdout=True)
        def foo():
            print("Foobar!")

        @flow_builder
        def my_flow(flow):
            foo()
        ```

        Flow initializer arguments can be passed
        ```python
        import prefect
        from prefect import task
        from prefect.utilities.flows import flow_builder

        def say_name():
            prefect.context.logger.info(f"Hi, my name is {prefect.context.flow_id!r}")

        @flow_builder(name="my-custom-name")
        def my_flow(flow):
            say_name()
        ```

        Run and register arguments can be passed as well for when called as a script
        ```python
        from prefect.utilities.flows import flow_builder
        from prefect.executors import DaskExecutor

        @flow_builder(
            register_kwargs=dict(project_name="default"),
            run_kwargs=dict(executor=DaskExecutor()),
        )
        def my_flow(flow):
            pass
        ```
    """

    @wraps(fn)
    def fn_with_flow_ctx(*args, **kwargs) -> prefect.Flow:
        flow_kwargs.setdefault("name", fn.__name__.replace("_", "-"))
        with prefect.Flow(**flow_kwargs) as flow:
            fn(flow, *args, **kwargs)
        return flow

    run_or_register(
        fn_with_flow_ctx,
        run_kwargs=run_kwargs,
        register_kwargs=register_kwargs,
        __frames__=3,
    )

    return fn_with_flow_ctx


def resolve_flow(flow: ResolvesToFlow) -> prefect.Flow:
    """
    Resolves a callable into a flow type and enforces that it is a flow instance
    """
    resolved = flow() if callable(flow) else flow

    if not isinstance(resolved, prefect.Flow):
        raise TypeError(
            f"{flow} resolved to type {type(resolved)!r}, expected 'Flow' or subclass"
        )

    return resolved


def run_or_register(
    flow: ResolvesToFlow,
    run_kwargs: Dict[str, Any] = None,
    register_kwargs: Dict[str, Any] = None,
    __frames__: int = 1,
) -> None:
    """
    If the caller of this function was run as a script, the flow is either run or
    registered according to first script argument if provided, defaults to running the
    flow.

    Args:
        flow: The flow to run/register/track
        run_kwargs: kwargs to pass to flow.run()
        register_kwargs: kwargs to pass to flow.register()
        __frames__: The number of stack frames to go up when checking the __name__
            Exposed for the `flow_builder` decorator
    """
    run_kwargs = run_kwargs or {}
    register_kwargs = register_kwargs or {}

    # A bit of magic to get __name__ from the caller so they don't have to pass it
    frame = inspect.stack()[__frames__].frame
    caller__name__ = frame.f_globals.get("__name__")

    # Check if the caller of this was called as a script in which case we will
    # run or register the flow as called for in the config
    if caller__name__ != "__main__":
        return

    # Check the first argument
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "run"  # default to running locally

    if mode == "run":
        # Run the flow
        resolve_flow(flow).run(**run_kwargs)

    elif mode == "register":
        # Register the flow
        resolve_flow(flow).register(**register_kwargs)

    else:
        raise ValueError(f"Unexpected mode {mode!r} please use 'run' or 'register'")
