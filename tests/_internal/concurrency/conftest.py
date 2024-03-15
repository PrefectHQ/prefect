import threading
import time
from typing import List

import pytest

from prefect._internal.concurrency.inspection import stack_for_threads


@pytest.fixture(autouse=True)
def check_thread_leak():
    """
    Checks for threads created in a test and left running.
    """
    active_threads_start = threading.enumerate()

    yield

    start = time.time()
    while True:
        bad_threads = [
            thread
            for thread in threading.enumerate()
            if thread not in active_threads_start
        ]
        if not bad_threads:
            break
        else:
            time.sleep(0.01)

        # Give leaked threads a 5 second grace period to teardown
        if time.time() > start + 5:
            lines: List[str] = [f"{len(bad_threads)} thread(s) were leaked from test\n"]
            lines += [
                f"\t{hex(thread.ident)} - {thread.name}\n" for thread in bad_threads
            ]
            lines += stack_for_threads(*bad_threads)
            pytest.fail("\n".join(lines), pytrace=False)
