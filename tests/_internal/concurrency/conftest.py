import faulthandler
import sys
import threading
import time

import pytest


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

        # Wait 5 seconds to display the thread state
        if time.time() > start + 5:
            lines: list[str] = [f"{len(bad_threads)} thread(s) were leaked from test\n"]
            lines += [
                f"\t{hex(thread.ident)} - {thread.name}\n" for thread in bad_threads
            ]

            # TODO: This is the laziest way to dump the stacks. We could do something
            #       better in the future. See dask.distributed's implementation for
            #       inspiration.
            faulthandler.dump_traceback(sys.stderr, all_threads=True)

            pytest.fail("\n".join(lines), pytrace=False)
