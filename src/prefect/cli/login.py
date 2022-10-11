import subprocess
import webbrowser
from typing import Union
from urllib.parse import quote
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel, ValidationError
from typing_extensions import Literal

import prefect
from prefect.cli import app
from prefect.settings import PREFECT_CLOUD_URL

login_api = FastAPI()


class LoginSuccess(BaseModel):
    api_key: str
    workspace_id: UUID
    account_id: UUID


class LoginFailed(BaseModel):
    reason: str


class LoginResult(BaseModel):
    type: Literal["success", "failure"]
    content: Union[LoginSuccess, LoginFailed]


@login_api.post("/success")
def receive_login(payload: LoginSuccess):
    print(LoginResult(type="success", content=payload).json())
    return "success"


@login_api.post("/failure")
def receive_failure(payload: LoginFailed):
    print(LoginResult(type="failure", content=payload).json())
    return "received"


@app.command()
def login():
    cloud_api_url = PREFECT_CLOUD_URL.value()

    process = subprocess.Popen(
        [
            "uvicorn",
            "--app-dir",
            str(prefect.__module_path__.parent),
            "--host",
            "127.0.0.1",
            "--port",
            str(3001),
            # "--log-level",
            # "critical",
            "prefect.cli.login:login_api",
        ],
        stdout=subprocess.PIPE,
    )

    target = quote("http://localhost:3001")

    # TODO: Create a separate setting for this?
    cloud_ui_url = cloud_api_url.replace("https://api.", "https://")
    ui_login_url = cloud_ui_url.replace("/api", f"/authorize?callback={target}")

    app.console.print("Opening browser...")
    webbrowser.open_new_tab(ui_login_url)

    app.console.print("Waiting for response...")
    # Quit after some time?
    output = None
    while not output:
        output = process.stdout.readline().strip()
    try:
        payload = LoginResult.parse_raw(output)
    except ValidationError:
        print(f"Invalid response from API: {output}")
    else:
        print(f":) got {payload!r}")

    process.kill()
