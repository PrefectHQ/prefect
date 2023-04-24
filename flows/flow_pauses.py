import os
import sys
import threading
import time
from concurrent.futures import Future

from packaging.version import Version

import prefect

# The version pauses were added in
PAUSE_VERSION = Version("2.7.0")
SERVER_VERSION = os.getenv("TEST_SERVER_VERSION")

if Version(prefect.__version__) < PAUSE_VERSION or (
    SERVER_VERSION and Version(SERVER_VERSION) < PAUSE_VERSION
):
    sys.exit(0)
else:
    from prefect import flow, pause_flow_run, resume_flow_run, task
    from prefect.context import get_run_context

flow_run_id_future = Future()


@task
def my_task():
    return 2 * 2


@flow
def pause_test():
    my_task()
    flow_run_id_future.set_result(get_run_context().flow_run.id)
    pause_flow_run()
    my_task()


def resume_after_started():
    print("Waiting for flow run id to be reported...")
    flow_run_id = flow_run_id_future.result()
    time.sleep(5)
    print("Resuming flow run...")
    resume_flow_run(flow_run_id)


if __name__ == "__main__":
    threading.Thread(target=resume_after_started, daemon=True).start()
    pause_test()
