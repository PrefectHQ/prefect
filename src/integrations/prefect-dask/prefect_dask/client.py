import asyncio
from uuid import uuid4

from distributed import Client, Future

from prefect.context import serialize_context
from prefect.task_engine import run_task_async, run_task_sync
from prefect.tasks import Task
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.engine import collect_task_run_inputs_sync


def _materialize_payload(value):
    return value


def _run_prefect_task(*args, **kwargs):
    task = kwargs["task"]
    if task.isasync:
        return asyncio.run(run_task_async(*args, **kwargs))
    else:
        return run_task_sync(*args, **kwargs)


class PrefectDaskClient(Client):
    def _submit_payload(self, value, key_prefix: str) -> Future:
        """Submit payload data as a dependency without waiting for a worker."""
        return super().submit(
            _materialize_payload,
            value,
            key=f"{key_prefix}-{uuid4().hex}",
            pure=False,
        )

    def _submit_prefect_run(
        self,
        run_task_kwargs,
        *,
        key,
        workers,
        resources,
        retries,
        priority,
        fifo_timeout,
        allow_other_workers,
        actor,
        actors,
        pure,
    ) -> Future:
        return super().submit(
            _run_prefect_task,
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

    def _submit_prefect_task(
        self,
        func: Task,
        task_future: Future,
        args,
        *,
        key,
        workers,
        resources,
        retries,
        priority,
        fifo_timeout,
        allow_other_workers,
        actor,
        actors,
        pure,
        kwargs,
    ) -> Future:
        kwargs = kwargs.copy()
        run_task_kwargs = {"task": task_future}
        task_run_id = uuid4()
        run_task_kwargs["task_run_id"] = task_run_id

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

        context = serialize_context(
            asset_ctx_kwargs={
                "task": func,
                "task_run_id": task_run_id,
                "task_inputs": dependencies,
                "copy_to_child_ctx": True,
            }
        )
        context_future = self._submit_payload(context, "prefect-context")
        run_task_kwargs["context"] = context_future

        if key is None:
            key = f"{func.name}-{uuid4().hex}"

        try:
            future = self._submit_prefect_run(
                run_task_kwargs,
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
            )
        finally:
            context_future.release()

        future.task_run_id = task_run_id
        return future

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
            task_future = self._submit_payload(func, "prefect-task")
            try:
                return self._submit_prefect_task(
                    func,
                    task_future,
                    args,
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
                    kwargs=kwargs,
                )
            finally:
                task_future.release()
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
            task_future = self._submit_payload(func, "prefect-task")
            try:
                futures = []
                for args in zip(*iterables):
                    futures.append(
                        self._submit_prefect_task(
                            func,
                            task_future,
                            args,
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
                            kwargs=kwargs,
                        )
                    )
                return futures
            finally:
                task_future.release()
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
