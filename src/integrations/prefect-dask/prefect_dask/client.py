import asyncio
from functools import wraps
from uuid import uuid4

from distributed import Client, Future

from prefect.context import serialize_context
from prefect.task_engine import run_task_async, run_task_sync
from prefect.tasks import Task
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.engine import collect_task_run_inputs_sync


class PrefectDaskClient(Client):
    def submit(
        self,
        func,
        *args,
        key=None,
        workers=None,
        resources=None,
        retries=None,
        priority=0,
        fifo_timeout="100 ms",
        allow_other_workers=False,
        actor=False,
        actors=False,
        pure=True,
        **kwargs,
    ):
        if isinstance(func, Task):
            run_task_kwargs = {}
            run_task_kwargs["task"] = func
            run_task_kwargs["task_run_id"] = uuid4()
            run_task_kwargs["context"] = serialize_context()

            passed_dependencies = kwargs.pop("dependencies", None)
            run_task_kwargs["wait_for"] = kwargs.pop("wait_for", None)
            run_task_kwargs["return_type"] = kwargs.pop("return_type", "result")
            if (parameters := kwargs.get("parameters")) is None:
                # If parameters are not provided, we need to extract them from the function.
                # This case is when the PrefectDistributedClient is used directly without
                # the DaskTaskRunner.
                parameters = get_call_parameters(func, args, kwargs)
            run_task_kwargs["parameters"] = parameters
            dependencies = {
                k: collect_task_run_inputs_sync(v, future_cls=Future)
                for k, v in parameters.items()
            }
            if passed_dependencies:
                dependencies = {
                    k: v.union(passed_dependencies.get(k, set()))
                    for k, v in dependencies.items()
                }
            run_task_kwargs["dependencies"] = dependencies

            @wraps(func)
            def wrapper_func(*args, **kwargs):
                if func.isasync:
                    return asyncio.run(run_task_async(*args, **kwargs))
                else:
                    return run_task_sync(*args, **kwargs)

            future = super().submit(
                wrapper_func,
                key=key,
                workers=workers,
                resources=resources,
                retries=retries,
                priority=priority,
                fifo_timeout=fifo_timeout,
                allow_other_workers=allow_other_workers,
                actor=actor,
                actors=actors,
                pure=pure,
                **run_task_kwargs,
            )

            future.task_run_id = run_task_kwargs["task_run_id"]
            return future
        else:
            return super().submit(
                func,
                *args,
                key=key,
                workers=workers,
                resources=resources,
                retries=retries,
                priority=priority,
                fifo_timeout=fifo_timeout,
                allow_other_workers=allow_other_workers,
                actor=actor,
                actors=actors,
                pure=pure,
                **kwargs,
            )

    def map(
        self,
        func,
        *iterables,
        key=None,
        workers=None,
        retries=None,
        resources=None,
        priority=0,
        allow_other_workers=False,
        fifo_timeout="100 ms",
        actor=False,
        actors=False,
        pure=True,
        batch_size=None,
        **kwargs,
    ):
        if isinstance(func, Task):
            args_list = zip(*iterables)
            futures = []
            for args in args_list:
                futures.append(
                    self.submit(
                        func,
                        *args,
                        key=key,
                        workers=workers,
                        resources=resources,
                        retries=retries,
                        priority=priority,
                        fifo_timeout=fifo_timeout,
                        allow_other_workers=allow_other_workers,
                        actor=actor,
                        actors=actors,
                        pure=pure,
                        **kwargs,
                    )
                )
            return futures
        else:
            return super().map(
                func,
                *iterables,
                key=key,
                workers=workers,
                retries=retries,
                resources=resources,
                priority=priority,
                allow_other_workers=allow_other_workers,
                fifo_timeout=fifo_timeout,
                actor=actor,
                actors=actors,
                pure=pure,
                batch_size=batch_size,
                **kwargs,
            )
