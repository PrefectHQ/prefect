"""
Injected database interface dependencies
"""

import asyncio
from contextlib import ExitStack, contextmanager
from functools import wraps
from typing import Callable, Type, TypeVar

from typing_extensions import Concatenate, ParamSpec

from prefect.server.database.configurations import (
    AioSqliteConfiguration,
    AsyncPostgresConfiguration,
    BaseDatabaseConfiguration,
)
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
    BaseORMConfiguration,
)
from prefect.server.database.query_components import (
    AioSqliteQueryComponents,
    AsyncPostgresQueryComponents,
    BaseQueryComponents,
)
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

MODELS_DEPENDENCIES = {
    "database_config": None,
    "query_components": None,
    "orm": None,
    "interface_class": None,
}

P = ParamSpec("P")
R = TypeVar("R")


def provide_database_interface() -> PrefectDBInterface:
    """
    Get the current Prefect REST API database interface.

    If components of the interface are not set, defaults will be inferred
    based on the dialect of the connection URL.
    """
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()

    database_config = MODELS_DEPENDENCIES.get("database_config")
    query_components = MODELS_DEPENDENCIES.get("query_components")
    orm = MODELS_DEPENDENCIES.get("orm")
    interface_class = MODELS_DEPENDENCIES.get("interface_class")
    dialect = get_dialect(connection_url)

    if database_config is None:
        if dialect.name == "postgresql":
            database_config = AsyncPostgresConfiguration(connection_url=connection_url)
        elif dialect.name == "sqlite":
            database_config = AioSqliteConfiguration(connection_url=connection_url)
        else:
            raise ValueError(
                "Unable to infer database configuration from provided dialect. Got"
                f" dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["database_config"] = database_config

    if query_components is None:
        if dialect.name == "postgresql":
            query_components = AsyncPostgresQueryComponents()
        elif dialect.name == "sqlite":
            query_components = AioSqliteQueryComponents()
        else:
            raise ValueError(
                "Unable to infer query components from provided dialect. Got dialect"
                f" name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["query_components"] = query_components

    if orm is None:
        if dialect.name == "postgresql":
            orm = AsyncPostgresORMConfiguration()
        elif dialect.name == "sqlite":
            orm = AioSqliteORMConfiguration()
        else:
            raise ValueError(
                "Unable to infer orm configuration from provided dialect. Got dialect"
                f" name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["orm"] = orm

    if interface_class is None:
        interface_class = PrefectDBInterface

    return interface_class(
        database_config=database_config,
        query_components=query_components,
        orm=orm,
    )


def inject_db(fn: Callable) -> Callable:
    """
    Decorator that provides a database interface to a function.

    The decorated function _must_ take a `db` kwarg and if a db is passed
    when called it will be used instead of creating a new one.

    If the function is a coroutine function, the wrapper will await the
    function's result. Otherwise, the wrapper will call the function
    normally.
    """

    def inject(kwargs):
        if "db" not in kwargs or kwargs["db"] is None:
            kwargs["db"] = provide_database_interface()

    @wraps(fn)
    async def async_wrapper(*args, **kwargs):
        inject(kwargs)
        return await fn(*args, **kwargs)

    @wraps(fn)
    def sync_wrapper(*args, **kwargs):
        inject(kwargs)
        return fn(*args, **kwargs)

    if asyncio.iscoroutinefunction(fn):
        return async_wrapper

    return sync_wrapper


def db_injector(
    func: Callable[Concatenate[PrefectDBInterface, P], R],
) -> Callable[P, R]:
    """
    Decorator to inject a PrefectDBInterface instance as the first positional
    argument to the decorated function.

    Unlike `inject_db`, which injects the database connection as a keyword
    argument, `db_injector` adds it explicitly as the first positional
    argument. This change enhances type hinting by making the dependency on
    PrefectDBInterface explicit in the function signature.

    Args:
        func: The function to decorate, which can be either synchronous or
        asynchronous.

    Returns:
        A wrapped function with the PrefectDBInterface instance injected as the
        first argument, preserving the original function's other parameters and
        return type.
    """

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        db = provide_database_interface()
        return func(db, *args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        db = provide_database_interface()
        return await func(db, *args, **kwargs)  # type: ignore

    if asyncio.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    else:
        return sync_wrapper


@contextmanager
def temporary_database_config(tmp_database_config: BaseDatabaseConfiguration):
    """
    Temporarily override the Prefect REST API database configuration.
    When the context is closed, the existing database configuration will
    be restored.

    Args:
        tmp_database_config: Prefect REST API database configuration to inject.

    """
    starting_config = MODELS_DEPENDENCIES["database_config"]
    try:
        MODELS_DEPENDENCIES["database_config"] = tmp_database_config
        yield
    finally:
        MODELS_DEPENDENCIES["database_config"] = starting_config


@contextmanager
def temporary_query_components(tmp_queries: BaseQueryComponents):
    """
    Temporarily override the Prefect REST API database query components.
    When the context is closed, the existing query components will
    be restored.

    Args:
        tmp_queries: Prefect REST API query components to inject.

    """
    starting_queries = MODELS_DEPENDENCIES["query_components"]
    try:
        MODELS_DEPENDENCIES["query_components"] = tmp_queries
        yield
    finally:
        MODELS_DEPENDENCIES["query_components"] = starting_queries


@contextmanager
def temporary_orm_config(tmp_orm_config: BaseORMConfiguration):
    """
    Temporarily override the Prefect REST API ORM configuration.
    When the context is closed, the existing orm configuration will
    be restored.

    Args:
        tmp_orm_config: Prefect REST API ORM configuration to inject.

    """
    starting_orm_config = MODELS_DEPENDENCIES["orm"]
    try:
        MODELS_DEPENDENCIES["orm"] = tmp_orm_config
        yield
    finally:
        MODELS_DEPENDENCIES["orm"] = starting_orm_config


@contextmanager
def temporary_interface_class(tmp_interface_class: Type[PrefectDBInterface]):
    """
    Temporarily override the Prefect REST API interface class When the context is closed,
    the existing interface will be restored.

    Args:
        tmp_interface_class: Prefect REST API interface class to inject.

    """
    starting_interface_class = MODELS_DEPENDENCIES["interface_class"]
    try:
        MODELS_DEPENDENCIES["interface_class"] = tmp_interface_class
        yield
    finally:
        MODELS_DEPENDENCIES["interface_class"] = starting_interface_class


@contextmanager
def temporary_database_interface(
    tmp_database_config: BaseDatabaseConfiguration = None,
    tmp_queries: BaseQueryComponents = None,
    tmp_orm_config: BaseORMConfiguration = None,
    tmp_interface_class: Type[PrefectDBInterface] = None,
):
    """
    Temporarily override the Prefect REST API database interface.

    Any interface components that are not explicitly provided will be
    cleared and inferred from the Prefect REST API database connection string
    dialect.

    When the context is closed, the existing database interface will
    be restored.

    Args:
        tmp_database_config: An optional Prefect REST API database configuration to inject.
        tmp_orm_config: An optional Prefect REST API ORM configuration to inject.
        tmp_queries: Optional Prefect REST API query components to inject.
        tmp_interface_class: Optional database interface class to inject

    """
    with ExitStack() as stack:
        stack.enter_context(
            temporary_database_config(tmp_database_config=tmp_database_config)
        )
        stack.enter_context(temporary_query_components(tmp_queries=tmp_queries))
        stack.enter_context(temporary_orm_config(tmp_orm_config=tmp_orm_config))
        stack.enter_context(
            temporary_interface_class(tmp_interface_class=tmp_interface_class)
        )
        yield


def set_database_config(database_config: BaseDatabaseConfiguration):
    """Set Prefect REST API database configuration."""
    MODELS_DEPENDENCIES["database_config"] = database_config


def set_query_components(query_components: BaseQueryComponents):
    """Set Prefect REST API query components."""
    MODELS_DEPENDENCIES["query_components"] = query_components


def set_orm_config(orm_config: BaseORMConfiguration):
    """Set Prefect REST API orm configuration."""
    MODELS_DEPENDENCIES["orm"] = orm_config


def set_interface_class(interface_class: Type[PrefectDBInterface]):
    """Set Prefect REST API interface class."""
    MODELS_DEPENDENCIES["interface_class"] = interface_class
