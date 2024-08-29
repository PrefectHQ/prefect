"""
Defines the Prefect REST API FastAPI app.
"""

import asyncio
import atexit
import contextlib
import mimetypes
import os
import random
import shutil
import socket
import sqlite3
import subprocess
import time
from contextlib import asynccontextmanager
from functools import partial, wraps
from hashlib import sha256
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

import anyio
import asyncpg
import httpx
import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm.exc
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

import prefect
import prefect.server.api as api
import prefect.server.services as services
import prefect.settings
from prefect._internal.compatibility.experimental import enabled_experiments
from prefect.client.constants import SERVER_API_VERSION
from prefect.logging import get_logger
from prefect.server.api.dependencies import EnforceMinimumAPIVersion
from prefect.server.events import stream
from prefect.server.events.services.actions import Actions
from prefect.server.events.services.event_persister import EventPersister
from prefect.server.events.services.triggers import ProactiveTriggers, ReactiveTriggers
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.services.task_run_recorder import TaskRunRecorder
from prefect.server.utilities.database import get_dialect
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_LOG_RETRYABLE_ERRORS,
    PREFECT_DEBUG_MODE,
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS,
    PREFECT_UI_SERVE_BASE,
    get_current_settings,
)
from prefect.utilities.hashing import hash_objects
from prefect.utilities.processutils import get_sys_executable

TITLE = "Prefect Server"
API_TITLE = "Prefect Prefect REST API"
UI_TITLE = "Prefect Prefect REST API UI"
API_VERSION = prefect.__version__
# migrations should run only once per app start; the ephemeral API can potentially
# create multiple apps in a single process
LIFESPAN_RAN_FOR_APP = set()

logger = get_logger("server")

enforce_minimum_version = EnforceMinimumAPIVersion(
    # this should be <= SERVER_API_VERSION; clients that send
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
    api.concurrency_limits_v2.router,
    api.block_types.router,
    api.block_documents.router,
    api.workers.router,
    api.task_workers.router,
    api.work_queues.router,
    api.artifacts.router,
    api.block_schemas.router,
    api.block_capabilities.router,
    api.collections.router,
    api.variables.router,
    api.csrf_token.router,
    api.events.router,
    api.automations.router,
    api.templates.router,
    api.ui.flows.router,
    api.ui.flow_runs.router,
    api.ui.schemas.router,
    api.ui.task_runs.router,
    api.admin.router,
    api.root.router,
)

SQLITE_LOCKED_MSG = "database is locked"


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


class RequestLimitMiddleware:
    """
    A middleware that limits the number of concurrent requests handled by the API.

    This is a blunt tool for limiting SQLite concurrent writes which will cause failures
    at high volume. Ideally, we would only apply the limit to routes that perform
    writes.
    """

    def __init__(self, app, limit: float):
        self.app = app
        self._limiter = anyio.CapacityLimiter(limit)

    async def __call__(self, scope, receive, send) -> None:
        async with self._limiter:
            await self.app(scope, receive, send)


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
    logger.error("Encountered exception in request:", exc_info=True)
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


def is_client_retryable_exception(exc: Exception):
    if isinstance(exc, sqlalchemy.exc.OperationalError) and isinstance(
        exc.orig, sqlite3.OperationalError
    ):
        if getattr(exc.orig, "sqlite_errorname", None) in {
            "SQLITE_BUSY",
            "SQLITE_BUSY_SNAPSHOT",
        } or SQLITE_LOCKED_MSG in getattr(exc.orig, "args", []):
            return True
        else:
            # Avoid falling through to the generic `DBAPIError` case below
            return False

    if isinstance(
        exc,
        (
            sqlalchemy.exc.DBAPIError,
            asyncpg.exceptions.QueryCanceledError,
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.CannotConnectNowError,
            sqlalchemy.exc.InvalidRequestError,
            sqlalchemy.orm.exc.DetachedInstanceError,
        ),
    ):
        return True

    return False


def replace_placeholder_string_in_files(
    directory, placeholder, replacement, allowed_extensions=None
):
    """
    Recursively loops through all files in the given directory and replaces
    a placeholder string.
    """
    if allowed_extensions is None:
        allowed_extensions = [".txt", ".html", ".css", ".js", ".json", ".txt"]

    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in allowed_extensions):
                file_path = os.path.join(root, file)

                with open(file_path, "r", encoding="utf-8") as file:
                    file_data = file.read()

                file_data = file_data.replace(placeholder, replacement)

                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(file_data)


def copy_directory(directory, path):
    os.makedirs(path, exist_ok=True)
    for item in os.listdir(directory):
        source = os.path.join(directory, item)
        destination = os.path.join(path, item)

        if os.path.isdir(source):
            if os.path.exists(destination):
                shutil.rmtree(destination)
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination)


async def custom_internal_exception_handler(request: Request, exc: Exception):
    """
    Log a detailed exception for internal server errors before returning.

    Send 503 for errors clients can retry on.
    """
    if is_client_retryable_exception(exc):
        if PREFECT_API_LOG_RETRYABLE_ERRORS.value():
            logger.error("Encountered retryable exception in request:", exc_info=True)

        return JSONResponse(
            content={"exception_message": "Service Unavailable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    logger.error("Encountered exception in request:", exc_info=True)

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


def create_api_app(
    dependencies: Optional[List[Depends]] = None,
    health_check_path: str = "/health",
    version_check_path: str = "/version",
    fast_api_app_kwargs: Optional[Dict[str, Any]] = None,
) -> FastAPI:
    """
    Create a FastAPI app that includes the Prefect REST API

    Args:
        dependencies: a list of global dependencies to add to each Prefect REST API router
        health_check_path: the health check route path
        fast_api_app_kwargs: kwargs to pass to the FastAPI constructor

    Returns:
        a FastAPI app that serves the Prefect REST API
    """
    fast_api_app_kwargs = fast_api_app_kwargs or {}
    api_app = FastAPI(title=API_TITLE, **fast_api_app_kwargs)
    api_app.add_middleware(GZipMiddleware)

    @api_app.get(health_check_path, tags=["Root"])
    async def health_check():
        return True

    @api_app.get(version_check_path, tags=["Root"])
    async def server_version():
        return SERVER_API_VERSION

    # always include version checking
    if dependencies is None:
        dependencies = [Depends(enforce_minimum_version)]
    else:
        dependencies.append(Depends(enforce_minimum_version))

    for router in API_ROUTERS:
        api_app.include_router(router, dependencies=dependencies)

    return api_app


def create_ui_app(ephemeral: bool) -> FastAPI:
    ui_app = FastAPI(title=UI_TITLE)
    base_url = prefect.settings.PREFECT_UI_SERVE_BASE.value()
    cache_key = f"{prefect.__version__}:{base_url}"
    stripped_base_url = base_url.rstrip("/")
    static_dir = (
        prefect.settings.PREFECT_UI_STATIC_DIRECTORY.value()
        or prefect.__ui_static_subpath__
    )
    reference_file_name = "UI_SERVE_BASE"

    if os.name == "nt":
        # Windows defaults to text/plain for .js files
        mimetypes.init()
        mimetypes.add_type("application/javascript", ".js")

    @ui_app.get(f"{stripped_base_url}/ui-settings")
    def ui_settings():
        return {
            "api_url": prefect.settings.PREFECT_UI_API_URL.value(),
            "csrf_enabled": prefect.settings.PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value(),
            "flags": enabled_experiments(),
        }

    def reference_file_matches_base_url():
        reference_file_path = os.path.join(static_dir, reference_file_name)

        if os.path.exists(static_dir):
            try:
                with open(reference_file_path, "r") as f:
                    return f.read() == cache_key
            except FileNotFoundError:
                return False
        else:
            return False

    def create_ui_static_subpath():
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

        copy_directory(prefect.__ui_static_path__, static_dir)
        replace_placeholder_string_in_files(
            static_dir,
            "/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER",
            stripped_base_url,
        )

        # Create a file to indicate that the static files have been copied
        # This is used to determine if the static files need to be copied again
        # when the server is restarted
        with open(os.path.join(static_dir, reference_file_name), "w") as f:
            f.write(cache_key)

    ui_app.add_middleware(GZipMiddleware)

    if (
        os.path.exists(prefect.__ui_static_path__)
        and prefect.settings.PREFECT_UI_ENABLED.value()
        and not ephemeral
    ):
        # If the static files have already been copied, check if the base_url has changed
        # If it has, we delete the subpath directory and copy the files again
        if not reference_file_matches_base_url():
            create_ui_static_subpath()

        ui_app.mount(
            PREFECT_UI_SERVE_BASE.value(),
            SPAStaticFiles(directory=static_dir),
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

    import prefect.plugins
    from prefect.blocks.core import Block
    from prefect.server.models.block_registration import _load_collection_blocks_data
    from prefect.utilities.dispatch import get_registry_for_type

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if not PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value():
            await fn(*args, **kwargs)
            return

        # Ensure collections are imported and have the opportunity to register types
        # before loading the registry
        prefect.plugins.load_prefect_collections()

        blocks_registry = get_registry_for_type(Block)
        collection_blocks_data = await _load_collection_blocks_data()
        current_blocks_loading_hash = hash_objects(
            blocks_registry,
            collection_blocks_data,
            PREFECT_API_DATABASE_CONNECTION_URL.value(),
            hash_algo=sha256,
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
            logger.warning(
                ""
                f"Unable to read memo_store.toml from {PREFECT_MEMO_STORE_PATH} during "
                f"block auto-registration: {exc!r}.\n"
                "All blocks will be registered."
            )

        await fn(*args, **kwargs)

        if current_blocks_loading_hash is not None:
            try:
                if not memo_store_path.exists():
                    memo_store_path.touch(mode=0o0600)

                memo_store_path.write_text(
                    toml.dumps({"block_auto_registration": current_blocks_loading_hash})
                )
            except Exception as exc:
                logger.warning(
                    "Unable to write to memo_store.toml at"
                    f" {PREFECT_MEMO_STORE_PATH} after block auto-registration:"
                    f" {exc!r}.\n Subsequent server start ups will perform block"
                    " auto-registration, which may result in slower server startup."
                )

    return wrapper


def create_app(
    settings: Optional[prefect.settings.Settings] = None,
    ephemeral: bool = False,
    ignore_cache: bool = False,
) -> FastAPI:
    """
    Create an FastAPI app that includes the Prefect REST API and UI

    Args:
        settings: The settings to use to create the app. If not set, settings are pulled
            from the context.
        ignore_cache: If set, a new application will be created even if the settings
            match. Otherwise, an application is returned from the cache.
        ephemeral: If set, the application will be treated as ephemeral. The UI
            and services will be disabled.
    """
    settings = settings or prefect.settings.get_current_settings()
    cache_key = (settings.hash_key(), ephemeral)

    from prefect.logging.configuration import setup_logging

    setup_logging()

    if cache_key in APP_CACHE and not ignore_cache:
        return APP_CACHE[cache_key]

    # TODO: Move these startup functions out of this closure into the top-level or
    #       another dedicated location
    async def run_migrations():
        """Ensure the database is created and up to date with the current migrations"""
        if prefect.settings.PREFECT_API_DATABASE_MIGRATE_ON_START:
            from prefect.server.database.dependencies import provide_database_interface

            db = provide_database_interface()
            await db.create_db()

    @_memoize_block_auto_registration
    async def add_block_types():
        """Add all registered blocks to the database"""
        if not prefect.settings.PREFECT_API_BLOCKS_REGISTER_ON_START:
            return

        from prefect.server.database.dependencies import provide_database_interface
        from prefect.server.models.block_registration import run_block_auto_registration

        db = provide_database_interface()
        session = await db.session()

        async with session:
            await run_block_auto_registration(session=session)

    async def start_services():
        """Start additional services when the Prefect REST API starts up."""

        if ephemeral:
            app.state.services = None
            return

        service_instances = []
        if prefect.settings.PREFECT_API_SERVICES_SCHEDULER_ENABLED.value():
            service_instances.append(services.scheduler.Scheduler())
            service_instances.append(services.scheduler.RecentDeploymentsScheduler())

        if prefect.settings.PREFECT_API_SERVICES_LATE_RUNS_ENABLED.value():
            service_instances.append(services.late_runs.MarkLateRuns())

        if prefect.settings.PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED.value():
            service_instances.append(services.pause_expirations.FailExpiredPauses())

        if prefect.settings.PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED.value():
            service_instances.append(
                services.cancellation_cleanup.CancellationCleanup()
            )

        if prefect.settings.PREFECT_SERVER_ANALYTICS_ENABLED.value():
            service_instances.append(services.telemetry.Telemetry())

        if prefect.settings.PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED.value():
            service_instances.append(
                services.flow_run_notifications.FlowRunNotifications()
            )

        if prefect.settings.PREFECT_API_SERVICES_FOREMAN_ENABLED.value():
            service_instances.append(services.foreman.Foreman())

        if prefect.settings.PREFECT_API_SERVICES_TRIGGERS_ENABLED.value():
            service_instances.append(ReactiveTriggers())
            service_instances.append(ProactiveTriggers())
            service_instances.append(Actions())

        if prefect.settings.PREFECT_API_SERVICES_TASK_RUN_RECORDER_ENABLED:
            service_instances.append(TaskRunRecorder())

        if prefect.settings.PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED:
            service_instances.append(EventPersister())

        if prefect.settings.PREFECT_API_EVENTS_STREAM_OUT_ENABLED:
            service_instances.append(stream.Distributor())

        loop = asyncio.get_running_loop()

        app.state.services = {
            service: loop.create_task(service.start()) for service in service_instances
        }

        for service, task in app.state.services.items():
            logger.info(f"{service.name} service scheduled to start in-app")
            task.add_done_callback(partial(on_service_exit, service))

    async def stop_services():
        """Ensure services are stopped before the Prefect REST API shuts down."""
        if hasattr(app.state, "services") and app.state.services:
            await asyncio.gather(*[service.stop() for service in app.state.services])
            try:
                await asyncio.gather(
                    *[task.stop() for task in app.state.services.values()]
                )
            except Exception:
                # `on_service_exit` should handle logging exceptions on exit
                pass

    @asynccontextmanager
    async def lifespan(app):
        if app not in LIFESPAN_RAN_FOR_APP:
            try:
                await run_migrations()
                await add_block_types()
                await start_services()
                LIFESPAN_RAN_FOR_APP.add(app)
                yield
            finally:
                await stop_services()
        else:
            yield

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
        lifespan=lifespan,
    )
    api_app = create_api_app(
        fast_api_app_kwargs={
            "exception_handlers": {
                # NOTE: FastAPI special cases the generic `Exception` handler and
                #       registers it as a separate middleware from the others
                Exception: custom_internal_exception_handler,
                RequestValidationError: validation_exception_handler,
                sa.exc.IntegrityError: integrity_exception_handler,
                ObjectNotFoundError: prefect_object_not_found_exception_handler,
            }
        },
    )
    ui_app = create_ui_app(ephemeral)

    # middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Limit the number of concurrent requests when using a SQLite database to reduce
    # chance of errors where the database cannot be opened due to a high number of
    # concurrent writes
    if (
        get_dialect(prefect.settings.PREFECT_API_DATABASE_CONNECTION_URL.value()).name
        == "sqlite"
    ):
        app.add_middleware(RequestLimitMiddleware, limit=100)

    if prefect.settings.PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value():
        app.add_middleware(api.middleware.CsrfMiddleware)

    if prefect.settings.PREFECT_API_ENABLE_METRICS:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @api_app.get("/metrics")
        async def metrics():
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    api_app.mount(
        "/static",
        StaticFiles(
            directory=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "static"
            )
        ),
        name="static",
    )
    app.api_app = api_app
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


subprocess_server_logger = get_logger()


class SubprocessASGIServer:
    _instances: Dict[Union[int, None], "SubprocessASGIServer"] = {}
    _port_range = range(8000, 9000)

    def __new__(cls, port: Optional[int] = None, *args, **kwargs):
        """
        Return an instance of the server associated with the provided port.
        Prevents multiple instances from being created for the same port.
        """
        if port not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[port] = instance
        return cls._instances[port]

    def __init__(self, port: Optional[int] = None):
        # This ensures initialization happens only once
        if not hasattr(self, "_initialized"):
            self.port: Optional[int] = port
            self.server_process = None
            self.server = None
            self.running = False
            self._initialized = True

    def find_available_port(self):
        max_attempts = 10
        for _ in range(max_attempts):
            port = random.choice(self._port_range)
            if self.is_port_available(port):
                return port
            time.sleep(random.uniform(0.1, 0.5))  # Random backoff
        raise RuntimeError("Unable to find an available port after multiple attempts")

    @staticmethod
    def is_port_available(port: int):
        with contextlib.closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return True
            except socket.error:
                return False

    @property
    def address(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def api_url(self) -> str:
        return f"{self.address}/api"

    def start(self, timeout: Optional[int] = None):
        """
        Start the server in a separate process. Safe to call multiple times; only starts
        the server once.

        Args:
            timeout: The maximum time to wait for the server to start
        """
        if not self.running:
            if self.port is None:
                self.port = self.find_available_port()
            assert self.port is not None, "Port must be provided or available"
            subprocess_server_logger.info(f"Starting server on {self.address}")
            try:
                self.running = True
                self.server_process = self._run_uvicorn_command()
                atexit.register(self.stop)
                with httpx.Client() as client:
                    response = None
                    elapsed_time = 0
                    max_wait_time = (
                        timeout
                        or PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS.value()
                    )
                    while elapsed_time < max_wait_time:
                        if self.server_process.poll() == 3:
                            self.port = self.find_available_port()
                            self.server_process = self._run_uvicorn_command()
                            continue
                        try:
                            response = client.get(f"{self.api_url}/health")
                        except httpx.ConnectError:
                            pass
                        else:
                            if response.status_code == 200:
                                break
                        time.sleep(0.1)
                        elapsed_time += 0.1
                    if response:
                        response.raise_for_status()
                    if not response:
                        error_message = "Timed out while attempting to connect to ephemeral Prefect API server."
                        if self.server_process.poll() is not None:
                            error_message += f" Ephemeral server process exited with code {self.server_process.returncode}."
                        if self.server_process.stdout:
                            error_message += (
                                f" stdout: {self.server_process.stdout.read()}"
                            )
                        if self.server_process.stderr:
                            error_message += (
                                f" stderr: {self.server_process.stderr.read()}"
                            )
                        raise RuntimeError(error_message)
            except Exception:
                self.running = False
                raise

    def _run_uvicorn_command(self) -> subprocess.Popen:
        # used to turn off background services
        server_env = {
            "PREFECT_UI_ENABLED": "0",
        }
        return subprocess.Popen(
            args=[
                get_sys_executable(),
                "-m",
                "uvicorn",
                "--app-dir",
                # quote wrapping needed for windows paths with spaces
                f'"{prefect.__module_path__.parent}"',
                "--factory",
                "prefect.server.api.server:create_app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "error",
                "--lifespan",
                "on",
            ],
            env={
                **os.environ,
                **server_env,
                **get_current_settings().to_environment_variables(exclude_unset=True),
            },
        )

    def stop(self):
        if self.server_process:
            subprocess_server_logger.info(f"Stopping server on {self.address}")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            finally:
                self.server_process = None
        if self.port in self._instances:
            del self._instances[self.port]
        if self.running:
            self.running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
