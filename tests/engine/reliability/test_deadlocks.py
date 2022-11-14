import time

import pytest

from prefect import flow, task


@task
def add_one(x: int) -> int:
    return x + 1


@task
def subtract_ten(x: int) -> int:
    return x - 10


@task
def sleep(x: float):
    time.sleep(x)


@pytest.mark.skip(reason="Causes a deadlock.")
def test_map_wait_for_many_tasks():
    @flow
    def run(n):
        added = add_one.map(range(n))
        result = [subtract_ten(x, wait_for=added) for x in range(n)]

        return result

    run(500)


@pytest.mark.skip(reason="Causes a deadlock.")
def test_loop_wait_for_many_tasks():
    @flow
    def run(n):
        added = add_one.map(range(n))
        for x in range(n):
            subtract_ten.submit(x, wait_for=added)

    run(500)


@pytest.mark.skip(reason="Causes a deadlock.")
def test_sleep_wait_for():
    @flow
    def run(sleep_time: float, n: int):
        add_one.map(range(n), wait_for=[sleep.submit(sleep_time)])

    run(5, 50)
