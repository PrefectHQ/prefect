# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import time

import pytest

from prefect_server.utilities.tests import wait_for


def test_wait_for():
    t = time.time()
    wait_for(lambda: True, timeout=1)
    assert time.time() - t < 0.2


def test_wait_for_calls_multiple_times():
    TIMES = []

    def test_fn():
        TIMES.append(time.time())
        return len(TIMES) == 5

    t = time.time()
    wait_for(test_fn, timeout=1)
    assert time.time() - t > 0.4
    assert len(TIMES) == 5


def test_wait_for_fail():
    with pytest.raises(ValueError):
        t = time.time()
        wait_for(lambda: False, timeout=1)
        assert time.time() - t > 1
