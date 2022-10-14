"""
Defines the Orion FastAPI app.
"""

import asyncio
import mimetypes
import os
from functools import partial, wraps
from hashlib import sha256
from typing import Awaitable, Callable, Dict, List, Mapping, Optional, Tuple

import sqlalchemy as sa
from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

import prefect
import prefect.orion.api as api
import prefect.orion.services as services
import prefect.settings
from prefect.logging import get_logger
from prefect.orion.api.dependencies import EnforceMinimumAPIVersion
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.utilities.server import method_paths_from_routes
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
)
from prefect.utilities.hashing import hash_objects

TITLE = "Prefect Orion"
API_TITLE = "Prefect Orion API"
UI_TITLE = "Prefect Orion UI"
API_VERSION = prefect.__version__
ORION_API_VERSION = "0.8.2"

logger = get_logger("orion")

enforce_minimum_version = EnforceMinimumAPIVersion(
    # this should be <= ORION_API_VERSION; clients that send
    # a version header under this value will be rejected
    minimum_api_version="0.8.0",
    logger=logger,
)


API_ROUTERS = (
    api.flows.router,
    api.flow_runs.router,
    api.task_runs.router,
    api.flow_run_states.router,
    api.task_run_states.router,
    api.flow_run_notification_policies.router,
    api.deployments.router,
    api.saved_searches.router,
    api.logs.router,
    api.concurrency_limits.router,
    api.block_types.router,
    api.block_documents.router,
    api.work_queues.router,
    api.block_schemas.router,
    api.block_capabilities.router,
    api.ui.flow_runs.router,
    api.admin.router,
    api.root.router,
)


class SPAStaticFiles(StaticFiles):
    """
    Implementation of `StaticFiles` for serving single page applications.

    Adds `get_response` handling to ensure that when a resource isn't found the
    application still returns the index.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException:
            return await super().get_response("./index.html", scope)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Provide a detailed message for request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(
            {
                "exception_message": "Invalid request received.",
                "exception_detail": exc.errors(),
                "request_body": exc.body,
            }
        ),
    )


async def integrity_exception_handler(request: Request, exc: Exception):
    """Capture database integrity errors."""
    logger.error(f"Encountered exception in request:", exc_info=True)
    return JSONResponse(
        content={
            "detail": (
                "Data integrity conflict. This usually means a "
                "unique or foreign key constraint was violated. "
                "See server logs for details."
            )
        },
        status_code=status.HTTP_409_CONFLICT,
    )


async def custom_internal_exception_handler(request: Request, exc: Exception):
    """Log a detailed exception for internal server errors before returning."""
    logger.error(f"Encountered exception in request:", exc_info=True)
    return JSONResponse(
        content={"exception_message": "Internal Server Error"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def prefect_object_not_found_exception_handler(
    request: Request, exc: ObjectNotFoundError
):
    """Return 404 status code on object not found exceptions."""
    return JSONResponse(
        content={"exception_message": str(exc)}, status_code=status.HTTP_404_NOT_FOUND
    )


def create_orion_api(
    router_prefix: Optional[str] = "",
    dependencies: Optional[List[Depends]] = None,
    health_check_path: str = "/health",
    fast_api_app_kwargs: dict = None,
    router_overrides: Mapping[str, Optional[APIRouter]] = None,
) -> FastAPI:
    """
    Create a FastAPI app that includes the Orion API

    Args:
        router_prefix: a prefix to apply to all included routers
        dependencies: a list of global dependencies to add to each Orion router
        health_check_path: the health check route path
        fast_api_app_kwargs: kwargs to pass to the FastAPI constructor
        router_overrides: a mapping of route prefixes (i.e. "/admin") to new routers
            allowing the caller to override the default routers. If `None` is provided
            as a value, the default router will be dropped from the application.

    Returns:
        a FastAPI app that serves the Orion API
    """
    fast_api_app_kwargs = fast_api_app_kwargs or {}
    api_app = FastAPI(title=API_TITLE, **fast_api_app_kwargs)

    @api_app.get(health_check_path)
    async def health_check():
        return True

    # always include version checking
    if dependencies is None:
        dependencies = [Depends(enforce_minimum_version)]
    else:
        dependencies.append(Depends(enforce_minimum_version))

    routers = {router.prefix: router for router in API_ROUTERS}

    if router_overrides:
        for prefix, router in router_overrides.items():

            # We may want to allow this behavior in the future to inject new routes, but
            # for now this will be treated an as an exception
            if prefix not in routers:
                raise KeyError(
                    f"Router override provided for prefix that does not exist: {prefix!r}"
                )

            # Drop the existing router
            existing_router = routers.pop(prefix)

            # Replace it with a new router if provided
            if router is not None:

                if prefix != router.prefix:
                    # We may want to allow this behavior in the future, but it will
                    # break expectations without additional routing and is banned for
                    # now
                    raise ValueError(
                        f"Router override for {prefix!r} defines a different prefix "
                        f"{router.prefix!r}."
                    )

                existing_paths = method_paths_from_routes(existing_router.routes)
                new_paths = method_paths_from_routes(router.routes)
                if not existing_paths.issubset(new_paths):
                    raise ValueError(
                        f"Router override for {prefix!r} is missing paths defined by "
                        f"the original router: {existing_paths.difference(new_paths)}"
                    )

                routers[prefix] = router

    for router in routers.values():
        api_app.include_router(router, prefix=router_prefix, dependencies=dependencies)

    return api_app


def create_ui_app(ephemeral: bool) -> FastAPI:
    ui_app = FastAPI(title=UI_TITLE)

    if os.name == "nt":
        # Windows defaults to text/plain for .js files
        mimetypes.init()
        mimetypes.add_type("application/javascript", ".js")

    @ui_app.get("/ui-settings")
    def ui_settings():
        return {
            "api_url": prefect.settings.PREFECT_ORION_UI_API_URL.value(),
        }

    if (
        os.path.exists(prefect.__ui_static_path__)
        and prefect.settings.PREFECT_ORION_UI_ENABLED.value()
        and not ephemeral
    ):
        ui_app.mount(
            "/",
            SPAStaticFiles(directory=prefect.__ui_static_path__),
            name="ui_root",
        )

    return ui_app


APP_CACHE: Dict[Tuple[prefect.settings.Settings, bool], FastAPI] = {}


def _memoize_block_auto_registration(fn: Callable[[], Awaitable[None]]):
    """
    Decorator to handle skipping the wrapped function if the block registry has
    not changed since the last invocation
    """
    import toml

    from prefect.blocks.core import Block
    from prefect.orion.models.block_registration import _load_collection_blocks_data
    from prefect.utilities.dispatch import get_registry_for_type

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if not PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value():
            await fn(*args, **kwargs)
            return

        blocks_registry = get_registry_for_type(Block)
        collection_blocks_data = await _load_collection_blocks_data()
        current_blocks_loading_hash = hash_objects(
            blocks_registry, collection_blocks_data, hash_algo=sha256
        )

        memo_store_path = PREFECT_MEMO_STORE_PATH.value()
        try:
            if memo_store_path.exists():
                saved_blocks_loading_hash = toml.load(memo_store_path).get(
                    "block_auto_registration"
                )
                if (
                    saved_blocks_loading_hash is not None
                    and current_blocks_loading_hash == saved_blocks_loading_hash
                ):
                    if PREFECT_DEBUG_MODE.value():
                        logger.debug(
                            "Skipping block loading due to matching hash for block "
                            "auto-registration found in memo store."
                        )
                    return
        except Exception as exc:
            logger.warn(
                ""
                f"Unable to read memo_store.toml from {PREFECT_MEMO_STORE_PATH} during "
                f"block auto-registration: {exc!r}.\n"
                "All blocks will be registered."
            )

        await fn(*args, **kwargs)

        if current_blocks_loading_hash is not None:
            try:
                memo_store_path.write_text(
                    toml.dumps({"block_auto_registration": current_blocks_loading_hash})
                )
            except Exception as exc:
                logger.warn(
                    f"Unable to write to memo_store.toml at {PREFECT_MEMO_STORE_PATH} "
                    f"after block auto-registration: {exc!r}.\n Subsequent server start "
                    "ups will perform block auto-registration, which may result in "
                    "slower server startup."
                )

    return wrapper


def create_app(
    settings: prefect.settings.Settings = None,
    ephemeral: bool = False,
    ignore_cache: bool = False,
) -> FastAPI:
    """
    Create an FastAPI app that includes the Orion API and UI

    Args:
        settings: The settings to use to create the app. If not set, settings are pulled
            from the context.
        ignore_cache: If set, a new application will be created even if the settings
            match. Otherwise, an application is returned from the cache.
        ephemeral: If set, the application will be treated as ephemeral. The UI
            and services will be disabled.
    """
    settings = settings or prefect.settings.get_current_settings()
    cache_key = (settings, ephemeral)

    if cache_key in APP_CACHE and not ignore_cache:
        return APP_CACHE[cache_key]

    # TODO: Move these startup functions out of this closure into the top-level or
    #       another dedicated location
    async def run_migrations():
        """Ensure the database is created and up to date with the current migrations"""
        if prefect.settings.PREFECT_ORION_DATABASE_MIGRATE_ON_START:
            from prefect.orion.database.dependencies import provide_database_interface

            db = provide_database_interface()
            await db.create_db()

    @_memoize_block_auto_registration
    async def add_block_types():
        """Add all registered blocks to the database"""
        if not prefect.settings.PREFECT_ORION_BLOCKS_REGISTER_ON_START:
            return

        from prefect.orion.database.dependencies import provide_database_interface
        from prefect.orion.models.block_registration import run_block_auto_registration

        db = provide_database_interface()
        session = await db.session()

        try:
            async with session:
                await run_block_auto_registration(session=session)
        except Exception as exc:
            logger.warn(f"Error occurred during block auto-registration: {exc!r}")

    async def start_services():
        """Start additional services when the Orion API starts up."""

        if ephemeral:
            app.state.services = None
            return

        service_instances = []

        if prefect.settings.PREFECT_ORION_SERVICES_SCHEDULER_ENABLED.value():
            service_instances.append(services.scheduler.Scheduler())
            service_instances.append(services.scheduler.RecentDeploymentsScheduler())

        if prefect.settings.PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED.value():
            service_instances.append(services.late_runs.MarkLateRuns())

        if prefect.settings.PREFECT_ORION_ANALYTICS_ENABLED.value():
            service_instances.append(services.telemetry.Telemetry())

        if (
            prefect.settings.PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED.value()
        ):
            service_instances.append(
                services.flow_run_notifications.FlowRunNotifications()
            )

        loop = asyncio.get_running_loop()

        app.state.services = {
            service: loop.create_task(service.start()) for service in service_instances
        }

        for service, task in app.state.services.items():
            logger.info(f"{service.name} service scheduled to start in-app")
            task.add_done_callback(partial(on_service_exit, service))

    async def stop_services():
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

    app = FastAPI(
        title=TITLE,
        version=API_VERSION,
        on_startup=[
            run_migrations,
            add_block_types,
            start_services,
        ],
        on_shutdown=[stop_services],
    )
    api_app = create_orion_api(
        fast_api_app_kwargs={
            "exception_handlers": {
                Exception: custom_internal_exception_handler,
                RequestValidationError: validation_exception_handler,
                sa.exc.IntegrityError: integrity_exception_handler,
                ObjectNotFoundError: prefect_object_not_found_exception_handler,
            }
        }
    )
    ui_app = create_ui_app(ephemeral)

    # middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_app.mount(
        "/static",
        StaticFiles(
            directory=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "static"
            )
        ),
        name="static",
    )
    app.mount("/api", app=api_app, name="api")
    app.mount("/", app=ui_app, name="ui")

    def openapi():
        """
        Convenience method for extracting the user facing OpenAPI schema from the API app.

        This method is attached to the global public app for easy access.
        """
        partial_schema = get_openapi(
            title=API_TITLE,
            version=API_VERSION,
            routes=api_app.routes,
        )
        new_schema = partial_schema.copy()
        new_schema["paths"] = {}
        for path, value in partial_schema["paths"].items():
            new_schema["paths"][f"/api{path}"] = value

        new_schema["info"]["x-logo"] = {"url": "static/prefect-logo-mark-gradient.png"}
        return new_schema

    app.openapi = openapi

    APP_CACHE[cache_key] = app
    return app
