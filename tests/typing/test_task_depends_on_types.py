"""Type checking tests for Task.depends_on()

This file is meant to be checked by type checkers (mypy, pyright)
to ensure the depends_on method preserves type safety.
"""

from typing import List

from prefect import flow, task
from prefect.futures import PrefectFuture


@task
def int_task(x: int) -> int:
    return x + 1


@task
def str_task(s: str) -> str:
    return s.upper()


@task
def list_task(items: List[int]) -> List[int]:
    return [i * 2 for i in items]


def test_depends_on_preserves_types() -> None:
    """Verify type inference works correctly with depends_on"""

    @flow
    def my_flow() -> None:
        # Basic type inference
        future1: PrefectFuture[int] = int_task.submit(5)
        future2: PrefectFuture[str] = str_task.depends_on([future1]).submit("hello")

        # Return type is preserved
        result1: int = future1.result()
        assert isinstance(result1, int)
        result2: str = future2.result()
        assert isinstance(result2, str)

        # Multiple dependencies
        future3: PrefectFuture[List[int]] = list_task.depends_on(
            [future1, future2]
        ).submit([1, 2, 3])
        result3: List[int] = future3.result()
        assert isinstance(result3, list)

        # Chaining still returns Task with correct types
        configured_task = int_task.depends_on([future1])
        future4: PrefectFuture[int] = configured_task.submit(10)
        assert isinstance(future4, PrefectFuture)

        # Type errors should be caught:
        # This would be a type error: str_task.submit(123)
        # This would be a type error: wrong_result: str = future1.result()


def test_depends_on_with_none() -> None:
    """Test type inference with None dependencies"""

    @flow
    def my_flow() -> None:
        # None is valid
        future: PrefectFuture[int] = int_task.depends_on(None).submit(5)
        result: int = future.result()
        assert isinstance(result, int)

        # Empty list is valid
        future2: PrefectFuture[int] = int_task.depends_on([]).submit(5)
        result2: int = future2.result()
        assert isinstance(result2, int)


def test_depends_on_with_mixed_futures() -> None:
    """Test with different future types in dependencies"""

    @flow
    def my_flow() -> None:
        int_future: PrefectFuture[int] = int_task.submit(1)
        str_future: PrefectFuture[str] = str_task.submit("test")

        # Mixed dependency types are fine
        list_future: PrefectFuture[List[int]] = list_task.depends_on(
            [int_future, str_future]
        ).submit([1, 2, 3])

        result: List[int] = list_future.result()
        assert isinstance(result, list)


if __name__ == "__main__":
    # This file is primarily for type checking, not execution
    print(
        "Run type checkers on this file: mypy tests/typing/test_task_depends_on_types.py"
    )
