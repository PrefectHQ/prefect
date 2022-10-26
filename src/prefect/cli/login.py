import signal
import urllib.parse
import webbrowser
from typing import Union
from uuid import UUID

import anyio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing_extensions import Literal

from prefect.cli import app
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.settings import PREFECT_CLOUD_URL

login_api = FastAPI()

login_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginSuccess(BaseModel):
    api_key: str
    workspace_id: UUID
    account_id: UUID


class LoginFailed(BaseModel):
    reason: str


class LoginResult(BaseModel):
    type: Literal["success", "failure"]
    content: Union[LoginSuccess, LoginFailed]


class ServerExit(Exception):
    pass


@login_api.post("/success")
def receive_login(payload: LoginSuccess):
    login_api.extra["result"] = LoginResult(type="success", content=payload)
    login_api.extra["result-event"].set()


@login_api.post("/failure")
def receive_failure(payload: LoginFailed):
    login_api.extra["result"] = LoginResult(type="failure", content=payload)
    login_api.extra["result-event"].set()


async def serve_login_api(cancel_scope, task_status):
    task_status.started()

    config = uvicorn.Config(
        "prefect.cli.login:login_api", port=3001, log_level="critical"
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except anyio.get_cancelled_exc_class():
        pass  # Already cancelled, do not cancel again
    else:
        # Uvicorn overrides signal handlers so without this Ctrl-C is broken
        cancel_scope.cancel()


@app.command()
async def login():
    cloud_api_url = PREFECT_CLOUD_URL.value()

    target = urllib.parse.quote("http://localhost:3001")

    # TODO: Create a separate setting for this?
    cloud_ui_url = cloud_api_url.replace("https://api.", "https://")
    ui_login_url = cloud_ui_url.replace("/api", f"/authorize?callback={target}")

    result_event = login_api.extra["result-event"] = anyio.Event()

    async with anyio.create_task_group() as tg:

        await tg.start(serve_login_api, tg.cancel_scope)

        app.console.print("Opening browser...")
        webbrowser.open_new_tab(ui_login_url)

        async with anyio.move_on_after(120) as timeout_scope:
            app.console.print("Waiting for response...")
            await result_event.wait()

        # Uvicorn installs signal handlers, this is the cleanest way to shutdown the
        # login API
        signal.raise_signal(signal.SIGINT)

    result = login_api.extra.get("result")
    if not result:
        if timeout_scope.cancel_called:
            exit_with_error("Timed out while waiting for authorization.")
        else:
            exit_with_error(f"Aborted.")

    if result.type == "success":
        exit_with_success(f"Logged into account {result.content.account_id}")
    elif result.type == "failure":
        exit_with_success(f"Failed to login: {result.content.reason}")
