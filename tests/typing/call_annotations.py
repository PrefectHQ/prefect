"""Call-site typing contracts for `@task` and `@flow` calls.

Never executed — checked by pyright and mypy in CI. Each `assert_type` pins
how a public call shape resolves; `--verifytypes` cannot see these (#16547
was a pyright call-site regression, #17379 a mypy-only one). Calls that must
STAY errors carry suppression comments: both checkers flag unused
suppressions, so a lost error fails CI too.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=error

from typing_extensions import assert_type

from prefect import flow, task
from prefect.futures import PrefectFuture, PrefectFutureList
from prefect.states import State


@task
def sync_task(x: int, label: str = "") -> int:
    return x


@task
async def async_task(x: int, label: str = "") -> int:
    return x


@flow
def sync_flow(x: int) -> int:
    return x


@flow
async def async_flow(x: int) -> int:
    return x


@task(name="configured-task")
async def configured_async_task(x: int) -> int:
    return x


@task(retries=1)
def configured_sync_task(x: int) -> int:
    return x


@flow(name="configured-flow")
async def configured_async_flow(x: int) -> int:
    return x


def check_sync_task_calls() -> None:
    assert_type(sync_task(1), int)
    assert_type(sync_task(1, label="a"), int)
    assert_type(sync_task(1, return_state=True), State[int])
    assert_type(sync_task(1, return_state=False), int)
    assert_type(sync_task(1, wait_for=[]), int)
    assert_type(sync_task(1, wait_for=[], return_state=True), State[int])


async def check_async_task_calls() -> None:
    assert_type(await async_task(1), int)
    assert_type(await async_task(1, return_state=False), int)
    assert_type(await async_task(1, wait_for=[]), int)
    assert_type(async_task(1, return_state=True), State[int])


def check_task_submit() -> None:
    assert_type(sync_task.submit(1), PrefectFuture[int])
    assert_type(async_task.submit(1), PrefectFuture[int])
    assert_type(sync_task.submit(1, return_state=True), State[int])


def check_task_map() -> None:
    assert_type(sync_task.map([1, 2]), PrefectFutureList[int])
    assert_type(async_task.map([1, 2]), PrefectFutureList[int])


def check_sync_flow_calls() -> None:
    assert_type(sync_flow(1), int)
    assert_type(sync_flow(1, return_state=True), State[int])


async def check_async_flow_calls() -> None:
    assert_type(await async_flow(1), int)
    assert_type(await async_flow(1, return_state=True), State[int])


async def check_configured_decorator_calls() -> None:
    assert_type(configured_sync_task(1), int)
    assert_type(await configured_async_task(1), int)
    assert_type(configured_async_task(1, return_state=True), State[int])
    assert_type(configured_async_task.submit(1), PrefectFuture[int])
    assert_type(configured_async_task.map([1, 2]), PrefectFutureList[int])
    assert_type(await configured_async_flow(1), int)
    assert_type(await configured_async_flow(1, return_state=True), State[int])


def check_wrong_calls_stay_errors() -> None:
    sync_task("nope")  # type: ignore[call-overload]
    sync_task()  # type: ignore[call-overload]
    sync_flow("nope")  # type: ignore[call-overload]
