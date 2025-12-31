"""
Internal utility for sending error logs to Prefect from the entrypoint.

Usage:
    python -m prefect._internal.send_entrypoint_logs < /tmp/output.log
    python -m prefect._internal.send_entrypoint_logs /tmp/output.log

Reads PREFECT__FLOW_RUN_ID from environment. Exits silently on failure.
"""

import logging
import os
import sys
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import LogCreate
from prefect.types._datetime import now


def _send(content: str, flow_run_id: UUID | None) -> None:
    logs = [
        LogCreate(
            name="prefect.entrypoint",
            level=logging.ERROR,
            message=content,
            timestamp=now("UTC"),
            flow_run_id=flow_run_id,
        )
    ]
    with get_client(sync_client=True) as client:
        client.create_logs(logs)


def main() -> None:
    if len(sys.argv) > 1:
        content = open(sys.argv[1]).read()
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        return

    if not content.strip():
        return

    flow_run_id = None
    if env_val := os.environ.get("PREFECT__FLOW_RUN_ID"):
        try:
            flow_run_id = UUID(env_val)
        except ValueError:
            pass

    try:
        _send(content, flow_run_id)
    except Exception:
        pass


if __name__ == "__main__":
    main()
