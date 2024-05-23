from uuid import uuid4

from distributed import Client as DistributedClient
from distributed import Future as DistributedFuture

from prefect.context import serialize_context
from prefect.new_task_engine import run_task
from prefect.tasks import Task
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.engine import collect_task_run_inputs_sync


def collect_dependencies(parameters):
    def create_task_run_inputs(expr):
        pass


class PrefectDistributedClient(DistributedClient):
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
            task_run_id = uuid4()
            context = serialize_context()

            if not (parameters := kwargs.get("parameters")):
                # If parameters are not provided, we need to extract them from the function.
                # This case is when the PrefectDistributedClient is used directly without
                # the DaskTaskRunner.
                parameters = get_call_parameters(func, args, kwargs)
            dependencies = {
                k: collect_task_run_inputs_sync(v, future_cls=DistributedFuture)
                for k, v in parameters.items()
            }

            future = super().submit(
                run_task,
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
                task=func,
                context=context,
                task_run_id=task_run_id,
                wait_for=kwargs.get("wait_for"),
                parameters=parameters,
                dependencies=dependencies,
            )
            future.task_run_id = task_run_id
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
