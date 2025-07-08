import threading
import time
from concurrent.futures import Future

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


def test_flow_pauses():
    threading.Thread(target=resume_after_started, daemon=True).start()
    result = pause_test()
    # Test passes if the flow completes the pause/resume cycle without error
    assert result is None  # Flow doesn't return anything, just completes
