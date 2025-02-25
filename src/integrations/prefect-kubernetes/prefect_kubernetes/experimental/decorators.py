from __future__ import annotations

import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    NoReturn,
    Optional,
    TypeVar,
    overload,
)

from prefect_kubernetes.worker import KubernetesWorker
from typing_extensions import Literal, ParamSpec

from prefect import Flow, State
from prefect.futures import PrefectFuture
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import get_call_parameters

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


class InfrastructureBoundFlow(Flow[P, R]):
    def __init__(
        self,
        *args: Any,
        work_pool: str,
        job_variables: dict[str, Any],
        # TODO: Update this to use BaseWorker when the .submit method is moved to the base class
        worker_cls: type[KubernetesWorker],
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.work_pool = work_pool
        self.job_variables = job_variables
        self.worker_cls = worker_cls

    @classmethod
    def from_flow(
        cls,
        flow: Flow[P, R],
        work_pool: str,
        job_variables: dict[str, Any],
        worker_cls: type[KubernetesWorker],
    ) -> InfrastructureBoundFlow[P, R]:
        new = cls(
            flow.fn,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=worker_cls,
        )
        # Copy all attributes from the original flow
        for attr, value in flow.__dict__.items():
            setattr(new, attr, value)
        return new

    @overload
    def __call__(self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs) -> None:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Coroutine[Any, Any, T]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T: ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> Awaitable[State[T]]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]: ...

    def __call__(
        self,
        *args: "P.args",
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
        **kwargs: "P.kwargs",
    ):
        async def modified_call(
            *args: P.args,
            return_state: bool = False,
            # TODO: Handle wait_for once we have an asynchronous way to wait for futures
            wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
            **kwargs: P.kwargs,
        ) -> R | State[R]:
            async with self.worker_cls(work_pool_name=self.work_pool) as worker:
                parameters = get_call_parameters(self, args, kwargs)
                future = await worker.submit(
                    flow=self,
                    parameters=parameters,
                    job_variables=self.job_variables,
                )
                if return_state:
                    await future.wait_async()
                    return future.state
                return await future.aresult()

        if inspect.iscoroutinefunction(self.fn):
            return modified_call(
                *args, return_state=return_state, wait_for=wait_for, **kwargs
            )
        else:
            return run_coro_as_sync(
                modified_call(
                    *args,
                    return_state=return_state,
                    wait_for=wait_for,
                    **kwargs,
                )
            )


def kubernetes(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], Flow[P, R]]:
    """
    Decorator that binds execution of a flow to a Kubernetes work pool

    Args:
        work_pool: The name of the Kubernetes work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes import kubernetes

        @kubernetes(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in a Kubernetes job
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return InfrastructureBoundFlow.from_flow(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=KubernetesWorker,
        )

    return decorator
