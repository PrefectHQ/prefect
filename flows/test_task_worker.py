"""
Simple use of a task worker when PREFECT_API_AUTH_STRING is set.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import anyio

from prefect import task
from prefect.server.api.server import SubprocessASGIServer
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_SERVER_API_AUTH_STRING,
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    temporary_settings,
)

CLIENT_SECRET = SERVER_SECRET = "very-secret-server-auth-string"
CLIENT_DUMMY_API_KEY = "dummy-key-should-be-ignored"
STARTUP_TIMEOUT = 30
CONNECTION_TIMEOUT = 30

counter = 0


@task
def bump():
    global counter
    counter += 1


@asynccontextmanager
async def run_ephemeral_server_with_auth() -> AsyncGenerator[str, None]:
    """Starts and stops an ephemeral server requiring auth string."""
    server = None
    try:
        with temporary_settings(
            updates={
                PREFECT_SERVER_API_AUTH_STRING: SERVER_SECRET,
                PREFECT_SERVER_CSRF_PROTECTION_ENABLED: "true",
            }
        ):
            server = SubprocessASGIServer()
            server.start(timeout=STARTUP_TIMEOUT)
            yield server.api_url
    finally:
        if server and server.server_process:
            server.stop()


async def test_authed_task_worker():
    async with run_ephemeral_server_with_auth() as api_url:
        try:
            with temporary_settings(
                updates={
                    PREFECT_API_URL: api_url,
                    PREFECT_API_AUTH_STRING: CLIENT_SECRET,
                    PREFECT_API_KEY: CLIENT_DUMMY_API_KEY,  # pass this as a regression for https://github.com/PrefectHQ/prefect/issues/17971
                }
            ):
                bump.delay()

                with anyio.move_on_after(CONNECTION_TIMEOUT):
                    await bump.serve()

                assert counter == 1

            print("task worker connected successfully")

        except Exception as e:
            print(f"task worker failed to connect: {e!r}")
            raise
