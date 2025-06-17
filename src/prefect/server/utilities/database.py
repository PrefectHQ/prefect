"""
Utilities for interacting with Prefect REST API database and ORM layer.

Prefect supports both SQLite and Postgres. Many of these utilities
allow the Prefect REST API to seamlessly switch between the two.
"""

from __future__ import annotations

import datetime
import json
import operator
import re
import uuid
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Type,
    Union,
    overload,
)
from zoneinfo import ZoneInfo

import pydantic
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql.operators import (
    # these are all incompletely annotated
    ASTEXT,  # type: ignore
    CONTAINS,  # type: ignore
    HAS_ALL,  # type: ignore
    HAS_ANY,  # type: ignore
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.sql import functions, schema
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.operators import OperatorType
from sqlalchemy.sql.visitors import replacement_traverse
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine
from typing_extensions import (
    Concatenate,
    ParamSpec,
    TypeAlias,
    TypeVar,
)

from prefect.types._datetime import DateTime

P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)
T = TypeVar("T", infer_variance=True)

_SQLExpressionOrLiteral: TypeAlias = Union[sa.SQLColumnExpression[T], T]
_Function = Callable[P, R]
_Method = Callable[Concatenate[T, P], R]
_DBFunction: TypeAlias = Callable[Concatenate["PrefectDBInterface", P], R]
_DBMethod: TypeAlias = Callable[Concatenate[T, "PrefectDBInterface", P], R]

CAMEL_TO_SNAKE: re.Pattern[str] = re.compile(r"(?<!^)(?=[A-Z])")

if TYPE_CHECKING:
    from prefect.server.database.interface import PrefectDBInterface


@overload
def db_injector(func: _DBMethod[T, P, R]) -> _Method[T, P, R]: ...


@overload
def db_injector(func: _DBFunction[P, R]) -> _Function[P, R]: ...


def db_injector(
    func: Union[_DBMethod[T, P, R], _DBFunction[P, R]],
) -> Union[_Method[T, P, R], _Function[P, R]]:
    from prefect.server.database import db_injector

    return db_injector(func)


class GenerateUUID(functions.FunctionElement[uuid.UUID]):
    """
    Platform-independent UUID default generator.
    Note the actual functionality for this class is specified in the
    `compiles`-decorated functions below
    """

    name = "uuid_default"


@compiles(GenerateUUID, "postgresql")
def generate_uuid_postgresql(
    element: GenerateUUID, compiler: SQLCompiler, **kwargs: Any
) -> str:
    """
    Generates a random UUID in Postgres; requires the pgcrypto extension.
    """

    return "(GEN_RANDOM_UUID())"


@compiles(GenerateUUID, "sqlite")
def generate_uuid_sqlite(
    element: GenerateUUID, compiler: SQLCompiler, **kwargs: Any
) -> str:
    """
    Generates a random UUID in other databases (SQLite) by concatenating
    bytes in a way that approximates a UUID hex representation. This is
    sufficient for our purposes of having a random client-generated ID
    that is compatible with a UUID spec.
    """

    return """
    (
        lower(hex(randomblob(4)))
        || '-'
        || lower(hex(randomblob(2)))
        || '-4'
        || substr(lower(hex(randomblob(2))),2)
        || '-'
        || substr('89ab',abs(random()) % 4 + 1, 1)
        || substr(lower(hex(randomblob(2))),2)
        || '-'
        || lower(hex(randomblob(6)))
    )
    """


class Timestamp(TypeDecorator[datetime.datetime]):
    """TypeDecorator that ensures that timestamps have a timezone.

    For SQLite, all timestamps are converted to UTC (since they are stored
    as naive timestamps without timezones) and recovered as UTC.
    """

    impl: TypeEngine[Any] | type[TypeEngine[Any]] = sa.TIMESTAMP(timezone=True)
    cache_ok: bool | None = True

    def load_dialect_impl(self, dialect: sa.Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TIMESTAMP(timezone=True))
        elif dialect.name == "sqlite":
            # see the sqlite.DATETIME docstring on the particulars of the storage
            # format. Note that the sqlite implementations for timestamp and interval
            # arithmetic below would require updating if a different format was to
            # be configured here.
            return dialect.type_descriptor(sqlite.DATETIME())
        else:
            return dialect.type_descriptor(sa.TIMESTAMP(timezone=True))

    def process_bind_param(
        self,
        value: Optional[datetime.datetime],
        dialect: sa.Dialect,
    ) -> Optional[datetime.datetime]:
        if value is None:
            return None
        else:
            if value.tzinfo is None:
                raise ValueError("Timestamps must have a timezone.")
            elif dialect.name == "sqlite":
                return value.astimezone(ZoneInfo("UTC"))
            else:
                return value

    def process_result_value(
        self,
        value: Optional[datetime.datetime],
        dialect: sa.Dialect,
    ) -> Optional[datetime.datetime]:
        # retrieve timestamps in their native timezone (or UTC)
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=ZoneInfo("UTC"))
            else:
                return value.astimezone(ZoneInfo("UTC"))


class UUID(TypeDecorator[uuid.UUID]):
    """
    Platform-independent UUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(36), storing as stringified hex values with
    hyphens.
    """

    impl: type[TypeEngine[Any]] | TypeEngine[Any] = TypeEngine
    cache_ok: bool | None = True

    def load_dialect_impl(self, dialect: sa.Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: Optional[Union[str, uuid.UUID]], dialect: sa.Dialect
    ) -> Optional[str]:
        if value is None:
            return None
        elif dialect.name == "postgresql":
            return str(value)
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return str(uuid.UUID(value))

    def process_result_value(
        self, value: Optional[Union[str, uuid.UUID]], dialect: sa.Dialect
    ) -> Optional[uuid.UUID]:
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class JSON(TypeDecorator[Any]):
    """
    JSON type that returns SQLAlchemy's dialect-specific JSON types, where
    possible. Uses generic JSON otherwise.

    The "base" type is postgresql.JSONB to expose useful methods prior
    to SQL compilation
    """

    impl: type[postgresql.JSONB] | type[TypeEngine[Any]] | TypeEngine[Any] = (
        postgresql.JSONB
    )
    cache_ok: bool | None = True

    def load_dialect_impl(self, dialect: sa.Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB(none_as_null=True))
        elif dialect.name == "sqlite":
            return dialect.type_descriptor(sqlite.JSON(none_as_null=True))
        else:
            return dialect.type_descriptor(sa.JSON(none_as_null=True))

    def process_bind_param(
        self, value: Optional[Any], dialect: sa.Dialect
    ) -> Optional[Any]:
        """Prepares the given value to be used as a JSON field in a parameter binding"""
        if not value:
            return value

        # PostgreSQL does not support the floating point extrema values `NaN`,
        # `-Infinity`, or `Infinity`
        # https://www.postgresql.org/docs/current/datatype-json.html#JSON-TYPE-MAPPING-TABLE
        #
        # SQLite supports storing and retrieving full JSON values that include
        # `NaN`, `-Infinity`, or `Infinity`, but any query that requires SQLite to parse
        # the value (like `json_extract`) will fail.
        #
        # Replace any `NaN`, `-Infinity`, or `Infinity` values with `None` in the
        # returned value.  See more about `parse_constant` at
        # https://docs.python.org/3/library/json.html#json.load.
        return json.loads(json.dumps(value), parse_constant=lambda c: None)


class Pydantic(TypeDecorator[T]):
    """
    A pydantic type that converts inserted parameters to
    json and converts read values to the pydantic type.
    """

    impl = JSON
    cache_ok: bool | None = True

    @overload
    def __init__(
        self,
        pydantic_type: type[T],
        sa_column_type: Optional[Union[type[TypeEngine[Any]], TypeEngine[Any]]] = None,
    ) -> None: ...

    # This overload is needed to allow for typing special forms (e.g.
    # Union[...], etc.) as these can't be married with `type[...]`. Also see
    # https://github.com/pydantic/pydantic/pull/8923
    @overload
    def __init__(
        self: "Pydantic[Any]",
        pydantic_type: Any,
        sa_column_type: Optional[Union[type[TypeEngine[Any]], TypeEngine[Any]]] = None,
    ) -> None: ...

    def __init__(
        self,
        pydantic_type: type[T],
        sa_column_type: Optional[Union[type[TypeEngine[Any]], TypeEngine[Any]]] = None,
    ) -> None:
        super().__init__()
        self._pydantic_type = pydantic_type
        self._adapter = pydantic.TypeAdapter(self._pydantic_type)
        if sa_column_type is not None:
            self.impl: type[JSON] | type[TypeEngine[Any]] | TypeEngine[Any] = (
                sa_column_type
            )

    def process_bind_param(
        self, value: Optional[T], dialect: sa.Dialect
    ) -> Optional[str]:
        if value is None:
            return None

        value = self._adapter.validate_python(value)

        # sqlalchemy requires the bind parameter's value to be a python-native
        # collection of JSON-compatible objects. we achieve that by dumping the
        # value to a json string using the pydantic JSON encoder and re-parsing
        # it into a python-native form.
        return self._adapter.dump_python(value, mode="json")

    def process_result_value(
        self, value: Optional[Any], dialect: sa.Dialect
    ) -> Optional[T]:
        if value is not None:
            return self._adapter.validate_python(value)


def bindparams_from_clause(
    query: sa.ClauseElement,
) -> dict[str, sa.BindParameter[Any]]:
    """Retrieve all non-anonymous bind parameters defined in a SQL clause"""
    # we could use `traverse(query, {}, {"bindparam": some_list.append})` too,
    # but this private method builds on the SQLA query caching infrastructure
    # and so is more efficient.
    return {
        bp.key: bp
        for bp in query._get_embedded_bindparams()  # pyright: ignore[reportPrivateUsage]
        # Anonymous keys are always a printf-style template that starts with '%([seed]'
        # the seed is the id() of the bind parameter itself.
        if not bp.key.startswith(f"%({id(bp)}")
    }


# Platform-independent datetime and timedelta arithmetic functions


class date_add(functions.GenericFunction[DateTime]):
    """Platform-independent way to add a timestamp and an interval"""

    type: Timestamp = Timestamp()
    inherit_cache: bool = True

    def __init__(
        self,
        dt: _SQLExpressionOrLiteral[datetime.datetime],
        interval: _SQLExpressionOrLiteral[datetime.timedelta],
        **kwargs: Any,
    ):
        super().__init__(
            sa.type_coerce(dt, Timestamp()),
            sa.type_coerce(interval, sa.Interval()),
            **kwargs,
        )


class interval_add(functions.GenericFunction[datetime.timedelta]):
    """Platform-independent way to add two intervals."""

    type: sa.Interval = sa.Interval()
    inherit_cache: bool = True

    def __init__(
        self,
        i1: _SQLExpressionOrLiteral[datetime.timedelta],
        i2: _SQLExpressionOrLiteral[datetime.timedelta],
        **kwargs: Any,
    ):
        super().__init__(
            sa.type_coerce(i1, sa.Interval()),
            sa.type_coerce(i2, sa.Interval()),
            **kwargs,
        )


class date_diff(functions.GenericFunction[datetime.timedelta]):
    """Platform-independent difference of two timestamps. Computes d1 - d2."""

    type: sa.Interval = sa.Interval()
    inherit_cache: bool = True

    def __init__(
        self,
        d1: _SQLExpressionOrLiteral[datetime.datetime],
        d2: _SQLExpressionOrLiteral[datetime.datetime],
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sa.type_coerce(d1, Timestamp()), sa.type_coerce(d2, Timestamp()), **kwargs
        )


class date_diff_seconds(functions.GenericFunction[float]):
    """Platform-independent calculation of the number of seconds between two timestamps or from 'now'"""

    type: Type[sa.REAL[float]] = sa.REAL
    inherit_cache: bool = True

    def __init__(
        self,
        dt1: _SQLExpressionOrLiteral[datetime.datetime],
        dt2: Optional[_SQLExpressionOrLiteral[datetime.datetime]] = None,
        **kwargs: Any,
    ) -> None:
        args = (sa.type_coerce(dt1, Timestamp()),)
        if dt2 is not None:
            args = (*args, sa.type_coerce(dt2, Timestamp()))
        super().__init__(*args, **kwargs)


# timestamp and interval arithmetic implementations for PostgreSQL


@compiles(date_add, "postgresql")
@compiles(interval_add, "postgresql")
@compiles(date_diff, "postgresql")
def datetime_or_interval_add_postgresql(
    element: Union[date_add, interval_add, date_diff],
    compiler: SQLCompiler,
    **kwargs: Any,
) -> str:
    operation = operator.sub if isinstance(element, date_diff) else operator.add
    return compiler.process(operation(*element.clauses), **kwargs)


@compiles(date_diff_seconds, "postgresql")
def date_diff_seconds_postgresql(
    element: date_diff_seconds, compiler: SQLCompiler, **kwargs: Any
) -> str:
    # either 1 or 2 timestamps; if 1, subtract from 'now'
    dts: list[sa.ColumnElement[datetime.datetime]] = list(element.clauses)
    if len(dts) == 1:
        dts = [sa.func.now(), *dts]
    as_utc = (sa.func.timezone("UTC", dt) for dt in dts)
    return compiler.process(sa.func.extract("epoch", operator.sub(*as_utc)), **kwargs)


# SQLite implementations for the Timestamp and Interval arithmetic functions.
#
# The following concepts are at play here:
#
# - By default, SQLAlchemy stores Timestamp values formatted as ISO8601 strings
#   (with a space between the date and the time parts), with microsecond precision.
# - SQLAlchemy stores Interval values as a Timestamp, offset from the UNIX epoch.
# - SQLite processes timestamp values with _at most_ millisecond precision, and
#   only if you use the `juliandate()` function or the 'subsec' modifier for
#   the `unixepoch()` function (the latter requires SQLite 3.42.0, released
#   2023-05-16)
#
# In order for arthmetic to work well, you need to convert timestamps to
# fractional [Julian day numbers][JDN], and intervals to a real number
# by subtracting the UNIX epoch from their Julian day number representation.
#
# Once the result has been computed, the result needs to be converted back
# to an ISO8601 formatted string including any milliseconds. For an
# interval result, that means adding the UNIX epoch offset to it first.
#
# [JDN]: https://en.wikipedia.org/wiki/Julian_day

# SQLite strftime() format to output ISO8601 date and time with milliseconds
# This format must be parseable by the `datetime.fromisodatetime()` function,
# or if the SQLite implementation for Timestamp below is configured with a
# regex, then that it must target that regex.
#
# SQLite only provides millisecond precision, but past versions of SQLAlchemy
# defaulted to parsing with a regex that would treat fractional as a value in
# microseconds. To ensure maximum compatibility the current format should
# continue to format the fractional seconds as microseconds, so 6 digits.
SQLITE_DATETIME_FORMAT = sa.literal("%Y-%m-%d %H:%M:%f000", literal_execute=True)
"""The SQLite timestamp output format as a SQL literal string constant"""


SQLITE_EPOCH_JULIANDAYNUMBER = sa.literal(2440587.5, literal_execute=True)
"""The UNIX epoch, 1970-01-01T00:00:00.000000Z, expressed as a fractional Julain day number"""
SECONDS_PER_DAY = sa.literal(24 * 60 * 60.0, literal_execute=True)
"""The number of seconds in a day as a SQL literal, to convert fractional Julian days to seconds"""

_sqlite_now_constant = sa.literal("now", literal_execute=True)
"""The 'now' string constant, passed to SQLite datetime functions"""
_sqlite_strftime = partial(sa.func.strftime, SQLITE_DATETIME_FORMAT)
"""Format SQLite timestamp to a SQLAlchemy-compatible string"""


def _sqlite_strfinterval(
    offset: sa.ColumnElement[float],
) -> sa.ColumnElement[datetime.datetime]:
    """Format interval offset to a SQLAlchemy-compatible string"""
    return _sqlite_strftime(SQLITE_EPOCH_JULIANDAYNUMBER + offset)


def _sqlite_interval_offset(
    interval: _SQLExpressionOrLiteral[datetime.timedelta],
) -> sa.ColumnElement[float]:
    """Convert interval value to a fraction Julian day number REAL offset from UNIX epoch"""
    return sa.func.julianday(interval) - SQLITE_EPOCH_JULIANDAYNUMBER


@compiles(functions.now, "sqlite")
def current_timestamp_sqlite(
    element: functions.now, compiler: SQLCompiler, **kwargs: Any
) -> str:
    """Generates the current timestamp for SQLite"""
    return compiler.process(_sqlite_strftime(_sqlite_now_constant), **kwargs)


@compiles(date_add, "sqlite")
def date_add_sqlite(element: date_add, compiler: SQLCompiler, **kwargs: Any) -> str:
    dt, interval = element.clauses
    jdn, offset = sa.func.julianday(dt), _sqlite_interval_offset(interval)
    # dt + interval, as fractional Julian day number values
    return compiler.process(_sqlite_strftime(jdn + offset), **kwargs)


@compiles(interval_add, "sqlite")
def interval_add_sqlite(
    element: interval_add, compiler: SQLCompiler, **kwargs: Any
) -> str:
    offsets = map(_sqlite_interval_offset, element.clauses)
    # interval + interval, as fractional Julian day number values
    return compiler.process(_sqlite_strfinterval(operator.add(*offsets)), **kwargs)


@compiles(date_diff, "sqlite")
def date_diff_sqlite(element: date_diff, compiler: SQLCompiler, **kwargs: Any) -> str:
    jdns = map(sa.func.julianday, element.clauses)
    # timestamp - timestamp, as fractional Julian day number values
    return compiler.process(_sqlite_strfinterval(operator.sub(*jdns)), **kwargs)


@compiles(date_diff_seconds, "sqlite")
def date_diff_seconds_sqlite(
    element: date_diff_seconds, compiler: SQLCompiler, **kwargs: Any
) -> str:
    # either 1 or 2 timestamps; if 1, subtract from 'now'
    dts: list[sa.ColumnElement[Any]] = list(element.clauses)
    if len(dts) == 1:
        dts = [_sqlite_now_constant, *dts]
    as_jdn = (sa.func.julianday(dt) for dt in dts)
    # timestamp - timestamp, as a fractional Julian day number, times the number of seconds in a day
    return compiler.process(operator.sub(*as_jdn) * SECONDS_PER_DAY, **kwargs)


# PostgreSQL JSON(B) Comparator operators ported to SQLite


def _is_literal(elem: Any) -> bool:
    """Element is not a SQLAlchemy SQL construct"""
    # Copied from sqlalchemy.sql.coercions._is_literal
    return not (
        isinstance(elem, (sa.Visitable, schema.SchemaEventTarget))
        or hasattr(elem, "__clause_element__")
    )


def _postgresql_array_to_json_array(
    elem: sa.ColumnElement[Any],
) -> sa.ColumnElement[Any]:
    """Replace any postgresql array() literals with a json_array() function call

    Because an _empty_ array leads to a PostgreSQL error, array() is often
    coupled with a cast(); this function replaces arrays with or without
    such a cast.

    This allows us to map the postgres JSONB.has_any / JSONB.has_all operand to
    SQLite.

    Returns the updated expression.

    """

    def _replacer(element: Any, **kwargs: Any) -> Optional[Any]:
        # either array(...), or cast(array(...), ...)
        if isinstance(element, sa.Cast):
            element = element.clause
        if isinstance(element, postgresql.array):
            return sa.func.json_array(*element.clauses)
        return None

    opts: dict[str, Any] = {}
    return replacement_traverse(elem, opts, _replacer)


def _json_each(elem: sa.ColumnElement[Any]) -> sa.TableValuedAlias:
    """SQLite json_each() table-valued construct

    Configures a SQLAlchemy table-valued object with the minimum
    column definitions and correct configuration.

    """
    return sa.func.json_each(elem).table_valued("key", "value", joins_implicitly=True)


# sqlite JSON operator implementations.


def _sqlite_json_astext(
    element: sa.BinaryExpression[Any],
) -> sa.BinaryExpression[Any]:
    """Map postgres JSON.astext / JSONB.astext (`->>`) to sqlite json_extract()

    Without the `as_string()` call, SQLAlchemy outputs json_quote(json_extract(...))

    """
    return element.left[element.right].as_string()


def _sqlite_json_contains(
    element: sa.BinaryExpression[bool],
) -> sa.ColumnElement[bool]:
    """Map JSONB.contains() and JSONB.has_all() to a SQLite expression"""
    # left can be a JSON value as a (Python) literal, or a SQL expression for a JSON value
    # right can be a SQLA postgresql.array() literal or a SQL expression for a
    # JSON array (for .has_all()) or it can be a JSON value as a (Python)
    # literal or a SQL expression for a JSON object (for .contains())
    left, right = element.left, element.right

    # if either top-level operand is literal, convert to a JSON bindparam
    if _is_literal(left):
        left = sa.bindparam("haystack", left, expanding=True, type_=JSON)
    if _is_literal(right):
        right = sa.bindparam("needles", right, expanding=True, type_=JSON)
    else:
        # convert the array() literal used in JSONB.has_all() to a JSON array.
        right = _postgresql_array_to_json_array(right)

    jleft, jright = _json_each(left), _json_each(right)

    # compute equality by counting the number of distinct matches between the
    # left items and the right items (e.g. the number of rows resulting from a
    # join) and seeing if it exceeds the number of distinct keys in the right
    # operand.
    #
    # note that using distinct emulates postgres behavior to disregard duplicates
    distinct_matches = (
        sa.select(sa.func.count(sa.distinct(jleft.c.value)))
        .join(jright, onclause=jleft.c.value == jright.c.value)
        .scalar_subquery()
    )
    distinct_keys = sa.select(
        sa.func.count(sa.distinct(jright.c.value))
    ).scalar_subquery()

    return distinct_matches >= distinct_keys


def _sqlite_json_has_any(element: sa.BinaryExpression[bool]) -> sa.ColumnElement[bool]:
    """Map JSONB.has_any() to a SQLite expression"""
    # left can be a JSON value as a (Python) literal, or a SQL expression for a JSON value
    # right can be a SQLA postgresql.array() literal or a SQL expression for a JSON array
    left, right = element.left, element.right

    # convert the array() literal used in JSONB.has_all() to a JSON array.
    right = _postgresql_array_to_json_array(right)

    jleft, jright = _json_each(left), _json_each(right)

    # deal with "json array ?| [value, ...]"" vs "json object ?| [key, ...]" tests
    # if left is a JSON object, match keys, else match values; the latter works
    # for arrays and all JSON scalar types
    json_object = sa.literal("object", literal_execute=True)
    left_elem = sa.case(
        (sa.func.json_type(element.left) == json_object, jleft.c.key),
        else_=jleft.c.value,
    )

    return sa.exists().where(left_elem == jright.c.value)


# Map of SQLA postgresql JSON/JSONB operators and a function to rewrite
# a BinaryExpression with such an operator to their SQLite equivalent.
_sqlite_json_operator_map: dict[
    OperatorType, Callable[[sa.BinaryExpression[Any]], sa.ColumnElement[Any]]
] = {
    ASTEXT: _sqlite_json_astext,
    CONTAINS: _sqlite_json_contains,
    HAS_ALL: _sqlite_json_contains,  # "has all" is equivalent to "contains"
    HAS_ANY: _sqlite_json_has_any,
}


@compiles(sa.BinaryExpression, "sqlite")
def sqlite_json_operators(
    element: sa.BinaryExpression[Any],
    compiler: SQLCompiler,
    override_operator: Optional[OperatorType] = None,
    **kwargs: Any,
) -> str:
    """Intercept the PostgreSQL-only JSON / JSONB operators and translate them to SQLite"""
    operator = override_operator or element.operator
    if (handler := _sqlite_json_operator_map.get(operator)) is not None:
        return compiler.process(handler(element), **kwargs)
    # ignore reason: SQLA compilation hooks are not as well covered with type annotations
    return compiler.visit_binary(element, override_operator=operator, **kwargs)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]


class greatest(functions.ReturnTypeFromArgs[T]):
    inherit_cache: bool = True


@compiles(greatest, "sqlite")
def sqlite_greatest_as_max(
    element: greatest[Any], compiler: SQLCompiler, **kwargs: Any
) -> str:
    # TODO: SQLite MAX() is very close to PostgreSQL GREATEST(), *except* when
    # it comes to nulls: SQLite MAX() returns NULL if _any_ clause is NULL,
    # whereas PostgreSQL GREATEST() only returns NULL if _all_ clauses are NULL.
    #
    # A work-around is to use MAX() as an aggregate function instead, in a
    # subquery. This, however, would probably require a VALUES-like construct
    # that SQLA doesn't currently support for SQLite. You can [provide
    # compilation hooks for
    # this](https://github.com/sqlalchemy/sqlalchemy/issues/7228#issuecomment-1746837960)
    # but this would only be worth it if sa.func.greatest() starts being used on
    # values that include NULLs. Up until the time of this comment this hasn't
    # been an issue.
    return compiler.process(sa.func.max(*element.clauses), **kwargs)


def get_dialect(obj: Union[str, Session, sa.Engine]) -> type[sa.Dialect]:
    """
    Get the dialect of a session, engine, or connection url.

    Primary use case is figuring out whether the Prefect REST API is communicating with
    SQLite or Postgres.

    Example:
        ```python
        import prefect.settings
        from prefect.server.utilities.database import get_dialect

        dialect = get_dialect(PREFECT_API_DATABASE_CONNECTION_URL.value())
        if dialect.name == "sqlite":
            print("Using SQLite!")
        else:
            print("Using Postgres!")
        ```
    """
    if isinstance(obj, Session):
        assert obj.bind is not None
        obj = obj.bind.engine if isinstance(obj.bind, sa.Connection) else obj.bind

    if isinstance(obj, sa.engine.Engine):
        url = obj.url
    else:
        url = sa.engine.url.make_url(obj)

    return url.get_dialect()
