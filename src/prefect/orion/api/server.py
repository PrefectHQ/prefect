"""
Defines the Orion FastAPI app.
"""

import asyncio
from functools import partial
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

import prefect
from prefect import settings
from prefect.orion import api, services
from prefect.utilities.logging import get_logger
from prefect.orion.database.dependencies import MODELS_DEPENDENCIES

TITLE = "Prefect Orion"
API_TITLE = "Prefect Orion API"
UI_TITLE = "Prefect Orion UI"
API_VERSION = prefect.__version__


class SPAStaticFiles(StaticFiles):
    # This class overrides the get_response method
    # to ensure that when a resource isn't found the application still
    # returns the index.html file. This is required for SPAs
    # since in-app routing is handled by a single html file.
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            response = await super().get_response("./index.html", scope)
        return response


def create_app(database_config=None) -> FastAPI:

    MODELS_DEPENDENCIES["database_config"] = database_config

    app = FastAPI(title=TITLE, version=API_VERSION)
    api_app = FastAPI(title=API_TITLE)
    ui_app = FastAPI(title=UI_TITLE)
    logger = get_logger("orion")

    # middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # api routers
    api_app.include_router(api.admin.router)
    api_app.include_router(api.data.router)
    api_app.include_router(api.flows.router)
    api_app.include_router(api.flow_runs.router)
    api_app.include_router(api.task_runs.router)
    api_app.include_router(api.flow_run_states.router)
    api_app.include_router(api.task_run_states.router)
    api_app.include_router(api.deployments.router)
    api_app.include_router(api.saved_searches.router)

    api_app.mount(
        "/static",
        StaticFiles(
            directory=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "static"
            )
        ),
        name="static",
    )

    app.mount("/api", app=api_app)
    if os.path.exists(prefect.__ui_static_path__) and settings.orion.ui.enabled:
        ui_app.mount(
            "/",
            SPAStaticFiles(directory=prefect.__ui_static_path__, html=True),
            name="ui_root",
        )
        app.mount("/", app=ui_app, name="ui")
    else:
        pass

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=API_TITLE,
            version=API_VERSION,
            routes=app.routes,
        )
        openapi_schema["info"]["x-logo"] = {
            "url": "static/prefect-logo-mark-gradient.png"
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = openapi

    @app.on_event("startup")
    async def start_services():
        """Start additional services when the Orion API starts up."""
        if settings.orion.services.run_in_app:
            loop = asyncio.get_running_loop()
            service_instances = [
                services.scheduler.Scheduler(),
                services.late_runs.MarkLateRuns(),
            ]
            app.state.services = {
                service: loop.create_task(service.start())
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
        """Ensure services are stopped before the Orion API shuts down."""
        if app.state.services:
            await asyncio.gather(*[service.stop() for service in app.state.services])
            try:
                await asyncio.gather(
                    *[task.stop() for task in app.state.services.values()]
                )
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

    return app


app = create_app()
