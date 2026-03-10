from __future__ import annotations

import os
import threading
import time
from uuid import UUID

import prefect_shell
from prefect_shell import ShellOperation

import prefect
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.client.schemas.sorting import LogSort
from prefect.context import get_run_context
from prefect.settings import PREFECT_API_URL

FLOW_RUN_ID: UUID | None = None
FLOW_ERROR: BaseException | None = None
FLOW_DONE = threading.Event()
FLOW_STARTED = threading.Event()


def build_command(steps: int, sleep_seconds: float) -> str:
    return f"""
bash -c '
for i in $(seq 1 {steps}); do
  echo "[INFO] step=$i/{steps} status=processing range=<broad-range>"
  echo "[DEBUG] step=$i internal-state=<redacted>" >&2
  sleep {sleep_seconds}
done
echo "[INFO] completed successfully"
'
"""


@flow
def debug_flow(steps: int, sleep_seconds: float) -> None:
    global FLOW_RUN_ID

    FLOW_RUN_ID = get_run_context().flow_run.id
    FLOW_STARTED.set()
    ShellOperation(commands=[build_command(steps, sleep_seconds)]).run()  # type: ignore[arg-type]


def run_flow(steps: int, sleep_seconds: float) -> None:
    global FLOW_ERROR

    try:
        debug_flow(steps, sleep_seconds)
    except BaseException as exc:
        FLOW_ERROR = exc
    finally:
        FLOW_DONE.set()


def read_flow_run_logs(flow_run_id: UUID) -> list[object]:
    with get_client(sync_client=True) as client:
        return client.read_logs(
            log_filter=LogFilter(
                flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]),
            ),
            sort=LogSort.TIMESTAMP_ASC,
        )


def main() -> None:
    steps = int(os.environ.get("REPRO_STEPS", "6"))
    sleep_seconds = float(os.environ.get("REPRO_SLEEP_SECONDS", "2"))
    poll_seconds = float(os.environ.get("REPRO_POLL_SECONDS", "1"))
    post_wait_seconds = float(os.environ.get("REPRO_POST_WAIT_SECONDS", "3"))

    print(f"prefect={prefect.__version__}")
    print(f"prefect-shell={prefect_shell.__version__}")
    print(f"PREFECT_API_URL={PREFECT_API_URL.value()!r}")
    print(
        f"steps={steps} sleep={sleep_seconds} poll={poll_seconds} "
        f"post_wait={post_wait_seconds}"
    )

    flow_thread = threading.Thread(
        target=run_flow,
        args=(steps, sleep_seconds),
        daemon=True,
    )
    started_at = time.monotonic()
    flow_thread.start()

    if not FLOW_STARTED.wait(timeout=30):
        raise RuntimeError("Flow did not start within 30 seconds.")

    assert FLOW_RUN_ID is not None
    print(f"flow_run_id={FLOW_RUN_ID}")

    seen = 0
    while not FLOW_DONE.is_set():
        logs = read_flow_run_logs(FLOW_RUN_ID)
        if len(logs) != seen:
            newest = logs[-1]
            when = time.monotonic() - started_at
            print(
                f"t=+{when:05.1f}s server_logs={len(logs)} "
                f"last={newest.timestamp} {newest.name}: {newest.message!r}"
            )
            seen = len(logs)
        time.sleep(poll_seconds)

    flow_thread.join()

    if FLOW_ERROR is not None:
        raise FLOW_ERROR

    time.sleep(post_wait_seconds)
    logs = read_flow_run_logs(FLOW_RUN_ID)
    stream_logs = [
        log for log in logs if "stream output" in log.message or "stderr" in log.message
    ]

    print(f"final_server_logs={len(logs)}")
    print(f"final_stream_logs={len(stream_logs)}")
    for log in logs:
        print(f"server_log {log.timestamp} {log.name}: {log.message!r}")
    for log in stream_logs[-5:]:
        print(f"stream_log {log.timestamp} {log.name}: {log.message!r}")


if __name__ == "__main__":
    main()
