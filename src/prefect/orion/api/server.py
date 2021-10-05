"""
Defines the Orion FastAPI app.
"""

import asyncio
from functools import partial
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import prefect
from prefect import settings
from prefect.orion import api, services
from prefect.utilities.logging import get_logger

API_TITLE = "Prefect Orion"
API_VERSION = prefect.__version__

app = FastAPI(title=API_TITLE, version=API_VERSION)
logger = get_logger("orion")

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# routers
app.include_router(api.admin.router, prefix="/api")
app.include_router(api.data.router, prefix="/api")
app.include_router(api.flows.router, prefix="/api")
app.include_router(api.flow_runs.router, prefix="/api")
app.include_router(api.task_runs.router, prefix="/api")
app.include_router(api.flow_run_states.router, prefix="/api")
app.include_router(api.task_run_states.router, prefix="/api")
app.include_router(api.deployments.router, prefix="/api")
app.include_router(api.saved_searches.router, prefix="/api")


app.mount(
    "/static",
    StaticFiles(
        directory=os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
    ),
    name="static",
)

if os.path.exists(prefect.__ui_static_path__):
    app.mount("/ui", StaticFiles(directory=prefect.__ui_static_path__), name="ui")
else:
    pass


@app.get("/")
async def root():
    return HTMLResponse(open(prefect.__ui_static_path__ / "index.html").read())


def openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {"url": "static/prefect-logo-mark-gradient.png"}
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = openapi


@app.on_event("startup")
async def start_services():
    """Start additional services when the Orion API starts up."""
    if settings.orion.services.run_in_app:
        loop = asyncio.get_running_loop()
        service_instances = [
            services.agent.Agent(),
            services.scheduler.Scheduler(),
            services.late_runs.MarkLateRuns(),
        ]
        app.state.services = {
            service: loop.create_task(service.start()) for service in service_instances
        }

        for service, task in app.state.services.items():
            logger.info(f"{service.name} service scheduled to start in-app")
            task.add_done_callback(partial(on_service_exit, service))
    else:
        logger.info(
            "In-app services have been disabled and will need to be run separately."
        )
        app.state.services = None


@app.on_event("shutdown")
async def wait_for_service_shutdown():
    """Ensure services are stopped before the Orion API shuts down."""
    if app.state.services:
        await asyncio.gather(*[service.stop() for service in app.state.services])
        try:
            await asyncio.gather(*[task.stop() for task in app.state.services.values()])
        except Exception as exc:
            # `on_service_exit` should handle logging exceptions on exit
            pass


def on_service_exit(service, task):
    """
    Added as a callback for completion of services to log exit
    """
    try:
        # Retrieving the result will raise the exception
        task.result()
    except Exception:
        logger.error(f"{service.name} service failed!", exc_info=True)
    else:
        logger.info(f"{service.name} service stopped!")
