"""Process entrypoint for a Prefect flow run in an AWS Lambda MicroVM."""

from __future__ import annotations

import threading

from prefect.logging import get_logger
from prefect_aws.microvm.payload import InvalidRunHookPayload
from prefect_aws.microvm.server import HOOK_SERVER_PORT, LifecycleHookServer
from prefect_aws.microvm.supervisor import supervise_flow_run

logger = get_logger("prefect_aws.microvm")


def main(port: int = HOOK_SERVER_PORT) -> int:
    """
    Serve the lifecycle hooks, run the flow run from the first `/run` request,
    and return the process exit code.

    Args:
        port: The port to serve the lifecycle hooks on.

    Returns:
        0 if the flow run's process exited 0. 1 if the `/run` request was
        rejected or the flow run's process failed.
    """
    server = LifecycleHookServer(("0.0.0.0", port))
    threading.Thread(
        target=server.serve_forever, name="microvm-lifecycle-hooks", daemon=True
    ).start()

    run_request = server.wait_for_run_request()
    server.stop_serving()
    # Frees the hook port for flow code. Only the run and ready hooks are
    # enabled, so the runtime sends nothing after `/run`.
    server.server_close()
    if isinstance(run_request, InvalidRunHookPayload):
        return 1
    # The flow run is forked from this thread, so it runs on the child's main
    # thread, where the engine can install its signal handlers.
    return supervise_flow_run(run_request.payload)
