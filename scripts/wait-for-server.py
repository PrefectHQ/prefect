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
            print("Connecting", end="")
            while True:
                print(".", end="", flush=True)
                healthcheck_exc = await client.api_healthcheck()
                if healthcheck_exc is not None:
                    await anyio.sleep(1)
                else:
                    print(" Successful!")
                    break
            if healthcheck_exc is not None:
                raise RuntimeError(
                    "Timed out while attempting to connect to compatibility test"
                    " server."
                )


if __name__ == "__main__":
    try:
        anyio.run(main, sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TIMEOUT_SECONDS)
    except Exception as exc:
        print(exc)
        exit(1)
    else:
        exit(0)
