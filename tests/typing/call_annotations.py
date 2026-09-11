"""Call-site typing contracts for `@task` and `@flow` calls.

Never executed — checked by pyright and mypy in CI. Each `assert_type` pins
how a public call shape resolves; `--verifytypes` cannot see these (#16547
was a pyright call-site regression, #17379 a mypy-only one). Calls that must
STAY errors carry suppression comments: both checkers flag unused
suppressions, so a lost error fails CI too.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=error

from typing import TypeVar

from typing_extensions import assert_type

from prefect import flow, task
from prefect.futures import PrefectFuture, PrefectFutureList
from prefect.states import State

T = TypeVar("T")


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


@task
def generic_task(x: T) -> T:
    return x


@task(retries=1)
def configured_generic_task(x: T) -> T:
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


def check_generic_task_calls() -> None:
    assert_type(generic_task(1), int)
    assert_type(generic_task("a"), str)
    assert_type(generic_task.submit(1), PrefectFuture[int])
    assert_type(configured_generic_task(1), int)
    assert_type(configured_generic_task.submit("a"), PrefectFuture[str])


@task
def consume_list(values: list[int]) -> int:
    return sum(values)


@task
async def async_consume_list(values: list[int]) -> int:
    return sum(values)


@task
def consume_scalar(value: int, label: str = "") -> int:
    return value


@task
def str_task(x: str) -> str:
    return x


@task
def consume_pair(a: int, b: int) -> int:
    return a + b


@task
def consume_triple(a: int, b: int, c: int) -> int:
    return a + b + c


async def check_future_inputs_preserve_result_type() -> None:
    mapped_int_futures = sync_task.map([1, 2])
    int_future = sync_task.submit(1)

    # #17379: passing mapped futures into a consumer task
    assert_type(consume_list(mapped_int_futures), int)
    assert_type(consume_scalar(int_future), int)
    assert_type(consume_scalar(int_future, label="x"), int)
    assert_type(consume_list(mapped_int_futures, return_state=True), State[int])
    assert_type(await async_consume_list(mapped_int_futures), int)

    # depth 2: a future in the second positional slot
    assert_type(consume_pair(1, int_future), int)
    assert_type(consume_pair(int_future, int_future), int)
    # depth 1 with trailing positional values; slots after the future unchecked
    assert_type(consume_pair(int_future, 2), int)


def check_future_input_limits() -> None:
    mapped_int_futures = sync_task.map([1, 2])
    int_future = sync_task.submit(1)
    str_future = str_task.submit("a")

    # Element types of leading-position futures are checked under pyright,
    # which binds T0 through the Concatenate self-type. mypy does not and
    # accepts a mistyped future (known gap, python/typing#1163).
    consume_list(str_future)  # pyright: ignore[reportCallIssue, reportArgumentType]
    consume_scalar(str_future)  # pyright: ignore[reportCallIssue, reportArgumentType]
    consume_pair(1, str_future)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # Known limit: a future in a keyword position cannot match any overload —
    # parameter names are not expressible generically (python/typing#1163).
    consume_list(values=mapped_int_futures)  # type: ignore[arg-type]
    consume_scalar(1, label=int_future)  # type: ignore[call-overload]

    # Depth 3+ is unimplemented: each depth needs its own overload, and the
    # depth-2 mypy constraint carries over (the last peeled slot must be
    # future-only). A future in the third slot behind two values stays an
    # error until then.
    consume_triple(1, 2, int_future)  # type: ignore[call-overload]


def check_wrong_calls_stay_errors() -> None:
    sync_task("nope")  # type: ignore[call-overload]
    sync_task()  # type: ignore[call-overload]
    sync_flow("nope")  # type: ignore[call-overload]
