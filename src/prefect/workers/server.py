from fastapi import FastAPI
import uvicorn
from types import FrameType
import signal

app = FastAPI()


# This is a hack to make sure that the server shuts down when the main process is killed
# as running uvicorn in an async task group appears to prevent SIGINTs from being propagated
# leading to hung processes
# https://github.com/encode/uvicorn/issues/1579
@app.on_event("startup")
async def on_webserver_startup() -> None:
    default_sigint_handler = signal.getsignal(signal.SIGINT)

    def terminate_now(signum: int, frame: FrameType = None):
        default_sigint_handler(signum, frame)
        exit()

    signal.signal(signal.SIGINT, terminate_now)


@app.get("/health")
async def check_health():
    return {"status": "OK"}


async def run_healthcheck_server():
    config = uvicorn.Config(app, port=5000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
