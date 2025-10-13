# /// script
# dependencies = [
#   "anyio",
#   "prefect",
# ]
# ///
"""
Wait until the Prefect server returns a healthy response.

Defaults to a 120 second timeout. If the timeout is exceeded, an exit code of 1 is set.

Usage:

    wait-for-server.py [<timeout-in-seconds>]

Example:

    PREFECT_API_URL="http://localhost:4200" ./scripts/wait-for-server.py
"""

import sys

import anyio

from prefect.client.orchestration import get_client

DEFAULT_TIMEOUT_SECONDS = 120


async def main(timeout):
    with anyio.move_on_after(timeout):
        print("Retrieving client...")
        async with get_client() as client:
            print("Waiting for server to be ready", end="")
            readiness_exc = None
            while True:
                print(".", end="", flush=True)
                try:
                    # Check /ready endpoint which verifies lifespan completion
                    response = await client._client.get("/ready")
                    if response.status_code == 200 and response.json() is True:
                        print(" Server ready!")
                        readiness_exc = None
                        break
                except Exception as exc:
                    readiness_exc = exc
                await anyio.sleep(1)
            if readiness_exc is not None:
                raise RuntimeError(
                    "Timed out while waiting for server to complete initialization."
                )


if __name__ == "__main__":
    try:
        timeout = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TIMEOUT_SECONDS
        anyio.run(main, timeout)
    except Exception as exc:
        print(exc)
        exit(1)
    else:
        exit(0)
