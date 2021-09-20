# import prefect
import asyncio
from functools import partial
from sys import exc_info
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prefect.orion import api
from prefect.orion.schemas import schedules
from prefect.orion import services
from prefect import settings
from prefect.utilities.logging import get_logger

app = FastAPI(title="Prefect Orion", version="alpha")
logger = get_logger("orion")

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# routers
app.include_router(api.data.router)
app.include_router(api.flows.router)
app.include_router(api.flow_runs.router)
app.include_router(api.task_runs.router)
app.include_router(api.flow_run_states.router)
app.include_router(api.task_run_states.router)
app.include_router(api.deployments.router)


@app.get("/hello", tags=["debug"])
def hello():
    return "👋"


@app.get("/echo", tags=["debug"])
def echo(x: str):
    return x


@app.on_event("startup")
async def start_services():
    if settings.orion.services.run_in_app:
        loop = asyncio.get_running_loop()
        service_instances = [services.agent.Agent(), services.scheduler.Scheduler()]
        app.state.service_tasks = [
            loop.create_task(service.start(), name=service.name)
            for service in service_instances
        ]

        for service, task in zip(service_instances, app.state.service_tasks):
            logger.info(f"Started service {service.name}")
            task.add_done_callback(partial(on_service_exit, service))
    else:
        logger.info(
            "In-app services have been disabled and will need to be run separately."
        )
        app.state.service_tasks = None


@app.on_event("shutdown")
async def wait_for_service_shutdown():
    if app.state.service_tasks:
        for task in app.state.service_tasks:
            try:
                task.cancel()
                await task.result()
            except Exception as exc:
                # `warn_on_on_service_failure` should be handled by the `done_callback`
                pass


def on_service_exit(service, task):
    """
    Added as a callback for completion of services to log exit
    """
    try:
        # Retrieving the result will raise the exception
        task.result()
    except asyncio.CancelledError:
        logger.info(f"Service {service.name} stopped!")
    except Exception:
        logger.error(f"Service {service.name} failed!", exc_info=True)
