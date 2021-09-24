# import prefect
import asyncio
from functools import partial
from sys import exc_info

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import prefect
from prefect import settings
from prefect.orion import api, services
from prefect.utilities.logging import get_logger

app = FastAPI(title="Prefect Orion", version=prefect.__version__)
logger = get_logger("orion")

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# routers
app.include_router(api.admin.router)
app.include_router(api.data.router)
app.include_router(api.flows.router)
app.include_router(api.flow_runs.router)
app.include_router(api.task_runs.router)
app.include_router(api.flow_run_states.router)
app.include_router(api.task_run_states.router)
app.include_router(api.deployments.router)


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/docs")


@app.on_event("startup")
async def start_services():
    if settings.orion.services.run_in_app:
        loop = asyncio.get_running_loop()
        service_instances = [
            services.agent.Agent(),
            services.scheduler.Scheduler(),
        ]
        app.state.services = {
            service: loop.create_task(service.start(), name=service.name)
            for service in service_instances
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
