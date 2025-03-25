"""
Injected database interface dependencies
"""

import sys
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    Union,
    cast,
    overload,
)

from typing_extensions import (
    Concatenate,
    Never,
    ParamSpec,
    Self,
    TypeAlias,
    TypedDict,
    TypeVar,
)

from prefect.server.database.configurations import (
    AioSqliteConfiguration,
    AsyncPostgresConfiguration,
    BaseDatabaseConfiguration,
)
from prefect.server.utilities.database import get_dialect
from prefect.server.utilities.schemas import PrefectDescriptorBase
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

if TYPE_CHECKING:
    from prefect.server.database.interface import PrefectDBInterface
    from prefect.server.database.orm_models import BaseORMConfiguration
    from prefect.server.database.query_components import BaseQueryComponents

P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)
T = TypeVar("T", infer_variance=True)

_Function = Callable[P, R]
_Method = Callable[Concatenate[T, P], R]
_DBFunction: TypeAlias = Callable[Concatenate["PrefectDBInterface", P], R]
_DBMethod: TypeAlias = Callable[Concatenate[T, "PrefectDBInterface", P], R]


class _ModelDependencies(TypedDict):
    database_config: Optional[BaseDatabaseConfiguration]
    query_components: Optional["BaseQueryComponents"]
    orm: Optional["BaseORMConfiguration"]
    interface_class: Optional[type["PrefectDBInterface"]]


MODELS_DEPENDENCIES: _ModelDependencies = {
    "database_config": None,
    "query_components": None,
    "orm": None,
    "interface_class": None,
}


def provide_database_interface() -> "PrefectDBInterface":
    """
    Get the current Prefect REST API database interface.

    If components of the interface are not set, defaults will be inferred
    based on the dialect of the connection URL.
    """
    from prefect.server.database.interface import PrefectDBInterface
    from prefect.server.database.orm_models import (
        AioSqliteORMConfiguration,
        AsyncPostgresORMConfiguration,
    )
    from prefect.server.database.query_components import (
        AioSqliteQueryComponents,
        AsyncPostgresQueryComponents,
    )

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


def inject_db(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator that provides a database interface to a function.

    The decorated function _must_ take a `db` kwarg and if a db is passed
    when called it will be used instead of creating a new one.

    """

    # NOTE: this wrapper will not pass a iscoroutinefunction()
    # check unless the caller first uses inspect.unwrap()
    # or we start using inspect.markcoroutinefunction() (Python 3.12)
    # In the past this has only been an issue when @inject_db
    # was being used in tests.
    #
    # If this becomes an issue again in future, use the @db_injector decorator
    # instead.

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if "db" not in kwargs or kwargs["db"] is None:
            kwargs["db"] = provide_database_interface()
        return fn(*args, **kwargs)

    return wrapper


@overload
def db_injector(func: _DBMethod[T, P, R]) -> _Method[T, P, R]: ...


@overload
def db_injector(func: _DBFunction[P, R]) -> _Function[P, R]: ...


def db_injector(
    func: Union[_DBMethod[T, P, R], _DBFunction[P, R]],
) -> Union[_Method[T, P, R], _Function[P, R]]:
    """
    Decorator to inject a PrefectDBInterface instance as the first positional
    argument to the decorated function.

    Unlike `inject_db`, which injects the database connection as a keyword
    argument, `db_injector` adds it explicitly as the first positional
    argument. This change enhances type hinting by making the dependency on
    PrefectDBInterface explicit in the function signature.

    When decorating a coroutine function, the result will continue to pass the
    iscoroutinefunction() test.

    Args:
        func: The function or method to decorate.

    Returns:
        A wrapped descriptor object which injects the PrefectDBInterface instance
        as the first argument to the function or method. This handles method
        binding transparently.

    """
    return DBInjector(func)


class _FuncWrapper(Generic[P, R]):
    """Mixin class to delegate all attribute access to a wrapped function

    This helps compatibility and echos what the Python method wrapper object
    does, and makes subclasses transarent to many introspection techniques.

    """

    __slots__ = "_func"

    def __init__(self, func: Callable[P, R]) -> None:
        object.__setattr__(self, "_func", func)

    @property
    def __wrapped__(self) -> Callable[P, R]:
        """Access the underlying wrapped function"""
        return self._func

    if not TYPE_CHECKING:
        # Attribute hooks are guarded against typecheckers which then tend to
        # mark the class as 'anything goes' otherwise.

        def __getattr__(self, name: str) -> Any:
            return getattr(self._func, name)

        def __setattr__(self, name: str, value: Any) -> None:
            setattr(self._func, name, value)

        def __delattr__(self, name: str) -> None:
            delattr(self._func, name)

        if sys.version_info < (3, 10):
            # Python 3.9 inspect.iscoroutinefunction tests are not flexible
            # enough to accept this decorator, unfortunately enough. But
            # asyncio.iscoroutinefunction does check for a marker object that,
            # when found as func._is_coroutine lets you pass the test anyway.

            @property
            def _is_coroutine(self):
                """Python 3.9 asyncio.iscoroutinefunction work-around"""
                from asyncio import coroutines, iscoroutinefunction

                if iscoroutinefunction(self._func):
                    return getattr(coroutines, "_is_coroutine", None)


# Descriptor object responsible for injecting the PrefectDBInterface instance.
# It has no docstring to encourage Python to find the wrapped callable docstring
# instead.
class DBInjector(
    PrefectDescriptorBase,
    _FuncWrapper[P, R],
    Generic[T, P, R],
):
    __slots__ = ("__name__",)

    __name__: str

    if TYPE_CHECKING:

        @overload
        def __new__(cls, func: _DBMethod[T, P, R]) -> "DBInjector[T, P, R]": ...

        @overload
        def __new__(cls, func: _DBFunction[P, R]) -> "DBInjector[None, P, R]": ...

        def __new__(
            cls, func: Union[_DBMethod[T, P, R], _DBFunction[P, R]]
        ) -> Union["DBInjector[T, P, R]", "DBInjector[None, P, R]"]: ...

    def __init__(self, func: Union[_DBMethod[T, P, R], _DBFunction[P, R]]) -> None:
        super().__init__(cast(Callable[P, R], func))

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        db = provide_database_interface()
        func = cast(_DBFunction[P, R], self._func)
        return func(db, *args, **kwargs)

    def __set_name__(self, owner: type[T], name: str) -> None:
        object.__setattr__(self, "__name__", name)

    @overload
    def __get__(self, instance: None, owner: type[T]) -> Self: ...

    @overload
    def __get__(
        self, instance: T, owner: Optional[type[T]] = None
    ) -> "_DBInjectorMethod[T, P, R]": ...

    @overload
    def __get__(self, instance: None, owner: None) -> Never: ...

    def __get__(
        self, instance: Optional[T], owner: Optional[type[T]] = None
    ) -> Union[Self, "_DBInjectorMethod[T, P, R]"]:
        if instance is None:
            if owner is None:
                raise TypeError("__get__(None, None) is invalid")
            return self
        return _DBInjectorMethod(instance, self._func.__get__(instance))

    def __repr__(self) -> str:
        return f"<DBInjector({self._func.__qualname__} at {id(self):#x}>"

    # The __doc__ property can't be defined in a mix-in.

    @property
    def __doc__(self) -> Optional[str]:
        return getattr(self._func, "__doc__", None)

    @__doc__.setter
    def __doc__(self, doc: Optional[str]) -> None:
        self._func.__doc__ = doc

    @__doc__.deleter
    def __doc__(self) -> None:  # type: ignore  # pyright doesn't like the override but it is fine
        self._func.__doc__ = None


# Proxy object to handle db interface injecting for bound methods.
class _DBInjectorMethod(_FuncWrapper[P, R], Generic[T, P, R]):
    __slots__ = ("_owner",)
    _owner: T

    def __init__(self, owner: T, func: _DBFunction[P, R]) -> None:
        super().__init__(cast(Callable[P, R], func))
        object.__setattr__(self, "_owner", owner)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        db = provide_database_interface()
        func = cast(_DBFunction[P, R], self._func)
        return func(db, *args, **kwargs)

    @property
    def __self__(self) -> T:
        return self._owner

    def __repr__(self) -> str:
        return f"<bound _DBInjectorMethod({self._func.__qualname__} at {id(self):#x}>"

    # The __doc__ property can't be defined in a mix-in.

    @property
    def __doc__(self) -> Optional[str]:
        return getattr(self._func, "__doc__", None)

    @__doc__.setter
    def __doc__(self, doc: Optional[str]) -> None:
        self._func.__doc__ = doc

    @__doc__.deleter
    def __doc__(self) -> None:  # type: ignore  # pyright doesn't like the override but it is fine
        self._func.__doc__ = None


@contextmanager
def temporary_database_config(
    tmp_database_config: Optional[BaseDatabaseConfiguration],
) -> Generator[None, object, None]:
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
def temporary_query_components(
    tmp_queries: Optional["BaseQueryComponents"],
) -> Generator[None, object, None]:
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
def temporary_orm_config(
    tmp_orm_config: Optional["BaseORMConfiguration"],
) -> Generator[None, object, None]:
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
def temporary_interface_class(
    tmp_interface_class: Optional[type["PrefectDBInterface"]],
) -> Generator[None, object, None]:
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
    tmp_database_config: Optional[BaseDatabaseConfiguration] = None,
    tmp_queries: Optional["BaseQueryComponents"] = None,
    tmp_orm_config: Optional["BaseORMConfiguration"] = None,
    tmp_interface_class: Optional[type["PrefectDBInterface"]] = None,
) -> Generator[None, object, None]:
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


def set_database_config(database_config: Optional[BaseDatabaseConfiguration]) -> None:
    """Set Prefect REST API database configuration."""
    MODELS_DEPENDENCIES["database_config"] = database_config


def set_query_components(query_components: Optional["BaseQueryComponents"]) -> None:
    """Set Prefect REST API query components."""
    MODELS_DEPENDENCIES["query_components"] = query_components


def set_orm_config(orm_config: Optional["BaseORMConfiguration"]) -> None:
    """Set Prefect REST API orm configuration."""
    MODELS_DEPENDENCIES["orm"] = orm_config


def set_interface_class(interface_class: Optional[type["PrefectDBInterface"]]) -> None:
    """Set Prefect REST API interface class."""
    MODELS_DEPENDENCIES["interface_class"] = interface_class
