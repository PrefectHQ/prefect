"""
Utilities for interacting with Prefect REST API database and ORM layer.

Prefect supports both SQLite and Postgres. Many of these utilities
allow the Prefect REST API to seamlessly switch between the two.
"""

import datetime
import json
import re
import uuid
from typing import List, Optional, Union

import pendulum
import pydantic
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.sql.sqltypes import BOOLEAN
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine

camel_to_snake = re.compile(r"(?<!^)(?=[A-Z])")


class GenerateUUID(FunctionElement):
    """
    Platform-independent UUID default generator.
    Note the actual functionality for this class is specified in the
    `compiles`-decorated functions below
    """

    name = "uuid_default"


@compiles(GenerateUUID, "postgresql")
@compiles(GenerateUUID)
def _generate_uuid_postgresql(element, compiler, **kwargs):
    """
    Generates a random UUID in Postgres; requires the pgcrypto extension.
    """

    return "(GEN_RANDOM_UUID())"


@compiles(GenerateUUID, "sqlite")
def _generate_uuid_sqlite(element, compiler, **kwargs):
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


class Timestamp(TypeDecorator):
    """TypeDecorator that ensures that timestamps have a timezone.

    For SQLite, all timestamps are converted to UTC (since they are stored
    as naive timestamps without timezones) and recovered as UTC.
    """

    impl = sa.TIMESTAMP(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TIMESTAMP(timezone=True))
        elif dialect.name == "sqlite":
            return dialect.type_descriptor(
                sqlite.DATETIME(
                    # SQLite is very particular about datetimes, and performs all comparisons
                    # as alphanumeric comparisons without regard for actual timestamp
                    # semantics or timezones. Therefore, it's important to have uniform
                    # and sortable datetime representations. The default is an ISO8601-compatible
                    # string with NO time zone and a space (" ") delimiter between the date
                    # and the time. The below settings can be used to add a "T" delimiter but
                    # will require all other sqlite datetimes to be set similarly, including
                    # the custom default value for datetime columns and any handwritten SQL
                    # formed with `strftime()`.
                    #
                    # store with "T" separator for time
                    # storage_format=(
                    #     "%(year)04d-%(month)02d-%(day)02d"
                    #     "T%(hour)02d:%(minute)02d:%(second)02d.%(microsecond)06d"
                    # ),
                    # handle ISO 8601 with "T" or " " as the time separator
                    # regexp=r"(\d+)-(\d+)-(\d+)[T ](\d+):(\d+):(\d+).(\d+)",
                )
            )
        else:
            return dialect.type_descriptor(sa.TIMESTAMP(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        else:
            if value.tzinfo is None:
                raise ValueError("Timestamps must have a timezone.")
            elif dialect.name == "sqlite":
                return pendulum.instance(value).in_timezone("UTC")
            else:
                return value

    def process_result_value(self, value, dialect):
        # retrieve timestamps in their native timezone (or UTC)
        if value is not None:
            return pendulum.instance(value).in_timezone("utc")


class UUID(TypeDecorator):
    """
    Platform-independent UUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(36), storing as stringified hex values with
    hyphens.
    """

    impl = TypeEngine
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        elif dialect.name == "postgresql":
            return str(value)
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class JSON(TypeDecorator):
    """
    JSON type that returns SQLAlchemy's dialect-specific JSON types, where
    possible. Uses generic JSON otherwise.

    The "base" type is postgresql.JSONB to expose useful methods prior
    to SQL compilation
    """

    impl = postgresql.JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB(none_as_null=True))
        elif dialect.name == "sqlite":
            return dialect.type_descriptor(sqlite.JSON(none_as_null=True))
        else:
            return dialect.type_descriptor(sa.JSON(none_as_null=True))

    def process_bind_param(self, value, dialect):
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


class Pydantic(TypeDecorator):
    """
    A pydantic type that converts inserted parameters to
    json and converts read values to the pydantic type.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, pydantic_type, sa_column_type=None):
        super().__init__()
        self._pydantic_type = pydantic_type
        if sa_column_type is not None:
            self.impl = sa_column_type

    def process_bind_param(self, value, dialect) -> Optional[str]:
        if value is None:
            return None

        # parse the value to ensure it complies with the schema
        # (this will raise validation errors if not)
        adapter = pydantic.TypeAdapter(self._pydantic_type)
        value = adapter.validate_python(value)

        # sqlalchemy requires the bind parameter's value to be a python-native
        # collection of JSON-compatible objects. we achieve that by dumping the
        # value to a json string using the pydantic JSON encoder and re-parsing
        # it into a python-native form.
        return adapter.dump_python(value, mode="json")

    def process_result_value(self, value, dialect):
        if value is not None:
            # load the json object into a fully hydrated typed object
            return pydantic.TypeAdapter(self._pydantic_type).validate_python(value)


class now(FunctionElement):
    """
    Platform-independent "now" generator.
    """

    type = Timestamp()
    name = "now"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = True


@compiles(now, "sqlite")
def _current_timestamp_sqlite(element, compiler, **kwargs):
    """
    Generates the current timestamp for SQLite

    We need to add three zeros to the string representation because SQLAlchemy
    uses a regex expression which is expecting 6 decimal places (microseconds),
    but SQLite by default only stores 3 (milliseconds). This causes SQLAlchemy
    to interpret 01:23:45.678 as if it were 01:23:45.000678. By forcing SQLite
    to store an extra three 0's, we work around his issue.

    Note this only affects timestamps that we ask SQLite to issue in SQL (like
    the default value for a timestamp column); not datetimes provided by
    SQLAlchemy itself.
    """
    return "strftime('%Y-%m-%d %H:%M:%f000', 'now')"


@compiles(now)
def _current_timestamp(element, compiler, **kwargs):
    """
    Generates the current timestamp in standard SQL
    """
    return "CURRENT_TIMESTAMP"


class date_add(FunctionElement):
    """
    Platform-independent way to add a date and an interval.
    """

    type = Timestamp()
    name = "date_add"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, dt, interval):
        self.dt = dt
        self.interval = interval
        super().__init__()


@compiles(date_add, "postgresql")
@compiles(date_add)
def _date_add_postgresql(element, compiler, **kwargs):
    return compiler.process(
        sa.cast(element.dt, Timestamp()) + sa.cast(element.interval, sa.Interval())
    )


@compiles(date_add, "sqlite")
def _date_add_sqlite(element, compiler, **kwargs):
    """
    In sqlite, we represent intervals as datetimes after the epoch, following
    SQLAlchemy convention for the Interval() type.
    """

    dt = element.dt
    if isinstance(dt, datetime.datetime):
        dt = str(dt)

    interval = element.interval
    if isinstance(interval, datetime.timedelta):
        interval = str(pendulum.datetime(1970, 1, 1) + interval)

    return compiler.process(
        # convert to date
        sa.func.strftime(
            "%Y-%m-%d %H:%M:%f000",
            sa.func.julianday(dt)
            + (
                # convert interval to fractional days after the epoch
                sa.func.julianday(interval) - 2440587.5
            ),
        )
    )


class interval_add(FunctionElement):
    """
    Platform-independent way to add two intervals.
    """

    type = sa.Interval()
    name = "interval_add"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, i1, i2):
        self.i1 = i1
        self.i2 = i2
        super().__init__()


@compiles(interval_add, "postgresql")
@compiles(interval_add)
def _interval_add_postgresql(element, compiler, **kwargs):
    return compiler.process(
        sa.cast(element.i1, sa.Interval()) + sa.cast(element.i2, sa.Interval())
    )


@compiles(interval_add, "sqlite")
def _interval_add_sqlite(element, compiler, **kwargs):
    """
    In sqlite, we represent intervals as datetimes after the epoch, following
    SQLAlchemy convention for the Interval() type.

    Therefore the sum of two intervals is

    (i1 - epoch) + (i2 - epoch) = i1 + i2 - epoch
    """

    i1 = element.i1
    if isinstance(i1, datetime.timedelta):
        i1 = str(pendulum.datetime(1970, 1, 1) + i1)

    i2 = element.i2
    if isinstance(i2, datetime.timedelta):
        i2 = str(pendulum.datetime(1970, 1, 1) + i2)

    return compiler.process(
        # convert to date
        sa.func.strftime(
            "%Y-%m-%d %H:%M:%f000",
            sa.func.julianday(i1) + sa.func.julianday(i2) - 2440587.5,
        )
    )


class date_diff(FunctionElement):
    """
    Platform-independent difference of dates. Computes d1 - d2.
    """

    type = sa.Interval()
    name = "date_diff"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, d1, d2):
        self.d1 = d1
        self.d2 = d2
        super().__init__()


@compiles(date_diff, "postgresql")
@compiles(date_diff)
def _date_diff_postgresql(element, compiler, **kwargs):
    return compiler.process(
        sa.cast(element.d1, Timestamp()) - sa.cast(element.d2, Timestamp())
    )


@compiles(date_diff, "sqlite")
def _date_diff_sqlite(element, compiler, **kwargs):
    """
    In sqlite, we represent intervals as datetimes after the epoch, following
    SQLAlchemy convention for the Interval() type.
    """
    d1 = element.d1
    if isinstance(d1, datetime.datetime):
        d1 = str(d1)

    d2 = element.d2
    if isinstance(d2, datetime.datetime):
        d2 = str(d2)

    return compiler.process(
        # convert to date
        sa.func.strftime(
            "%Y-%m-%d %H:%M:%f000",
            # the epoch in julian days
            2440587.5
            # plus the date difference in julian days
            + sa.func.julianday(d1)
            - sa.func.julianday(d2),
        )
    )


class json_contains(FunctionElement):
    """
    Platform independent json_contains operator, tests if the
    `left` expression contains the `right` expression.

    On postgres this is equivalent to the @> containment operator.
    https://www.postgresql.org/docs/current/functions-json.html
    """

    type = BOOLEAN
    name = "json_contains"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, left, right):
        self.left = left
        self.right = right
        super().__init__()


@compiles(json_contains, "postgresql")
@compiles(json_contains)
def _json_contains_postgresql(element, compiler, **kwargs):
    return compiler.process(
        sa.type_coerce(element.left, postgresql.JSONB).contains(
            sa.type_coerce(element.right, postgresql.JSONB)
        ),
        **kwargs,
    )


def _json_contains_sqlite_fn(left, right, compiler, **kwargs):
    # if the value is literal, convert to a JSON string
    if isinstance(left, (list, dict, tuple, str)):
        left = json.dumps(left)

    # if the value is literal, convert to a JSON string
    if isinstance(right, (list, dict, tuple, str)):
        right = json.dumps(right)

    json_each_left = sa.func.json_each(left).alias("left")
    json_each_right = sa.func.json_each(right).alias("right")

    # compute equality by counting the number of distinct matches between
    # the left items and the right items (e.g. the number of rows resulting from a join)
    # and seeing if it exceeds the number of distinct keys in the right operand
    #
    # note that using distinct emulates postgres behavior to disregard duplicates
    distinct_matches = (
        sa.select(sa.func.count(sa.distinct(sa.literal_column("left.value"))))
        .select_from(json_each_left)
        .join(
            json_each_right,
            sa.literal_column("left.value") == sa.literal_column("right.value"),
        )
        .scalar_subquery()
    )

    distinct_keys = (
        sa.select(sa.func.count(sa.distinct(sa.literal_column("right.value"))))
        .select_from(json_each_right)
        .scalar_subquery()
    )

    return compiler.process(distinct_matches >= distinct_keys)


@compiles(json_contains, "sqlite")
def _json_contains_sqlite(element, compiler, **kwargs):
    return _json_contains_sqlite_fn(element.left, element.right, compiler, **kwargs)


class json_extract(FunctionElement):
    """
    Platform independent json_extract operator, extracts a value from a JSON
    field via key.

    On postgres this is equivalent to the ->> operator.
    https://www.postgresql.org/docs/current/functions-json.html
    """

    type = sa.Text()
    name = "json_extract"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, column: sa.Column, path: str, wrap_quotes: bool = False):
        self.column = column
        self.path = path
        self.wrap_quotes = wrap_quotes
        super().__init__()


@compiles(json_extract, "postgresql")
@compiles(json_extract)
def _json_extract_postgresql(element, compiler, **kwargs):
    return "%s ->> '%s'" % (compiler.process(element.column, **kwargs), element.path)


@compiles(json_extract, "sqlite")
def _json_extract_sqlite(element, compiler, **kwargs):
    path = element.path.replace("'", "''")  # escape single quotes for JSON path
    if element.wrap_quotes:
        path = f'"{path}"'
    return "JSON_EXTRACT(%s, '$.%s')" % (
        compiler.process(element.column, **kwargs),
        path,
    )


class json_has_any_key(FunctionElement):
    """
    Platform independent json_has_any_key operator.

    On postgres this is equivalent to the ?| existence operator.
    https://www.postgresql.org/docs/current/functions-json.html
    """

    type = BOOLEAN
    name = "json_has_any_key"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, json_expr, values: List):
        self.json_expr = json_expr
        if not all(isinstance(v, str) for v in values):
            raise ValueError("json_has_any_key values must be strings")
        self.values = values
        super().__init__()


@compiles(json_has_any_key, "postgresql")
@compiles(json_has_any_key)
def _json_has_any_key_postgresql(element, compiler, **kwargs):
    values_array = postgresql.array(element.values)
    # if the array is empty, postgres requires a type annotation
    if not element.values:
        values_array = sa.cast(values_array, postgresql.ARRAY(sa.String))

    return compiler.process(
        sa.type_coerce(element.json_expr, postgresql.JSONB).has_any(values_array),
        **kwargs,
    )


@compiles(json_has_any_key, "sqlite")
def _json_has_any_key_sqlite(element, compiler, **kwargs):
    # attempt to match any of the provided values at least once
    json_each = sa.func.json_each(element.json_expr).alias("json_each")
    return compiler.process(
        sa.select(1)
        .select_from(json_each)
        .where(
            sa.literal_column("json_each.value").in_(
                # manually set the bindparam key because the default will
                # include the `.` from the literal column name and sqlite params
                # must be alphanumeric. `unique=True` automatically suffixes the bindparam
                # if there are overlaps.
                sa.bindparam(key="json_each_values", value=element.values, unique=True)
            )
        )
        .exists(),
        **kwargs,
    )


class json_has_all_keys(FunctionElement):
    """Platform independent json_has_all_keys operator.

    On postgres this is equivalent to the ?& existence operator.
    https://www.postgresql.org/docs/current/functions-json.html
    """

    type = BOOLEAN
    name = "json_has_all_keys"
    # see https://docs.sqlalchemy.org/en/14/core/compiler.html#enabling-caching-support-for-custom-constructs
    inherit_cache = False

    def __init__(self, json_expr, values: List):
        self.json_expr = json_expr
        if isinstance(values, list) and not all(isinstance(v, str) for v in values):
            raise ValueError(
                "json_has_all_key values must be strings if provided as a literal list"
            )
        self.values = values
        super().__init__()


@compiles(json_has_all_keys, "postgresql")
@compiles(json_has_all_keys)
def _json_has_all_keys_postgresql(element, compiler, **kwargs):
    values_array = postgresql.array(element.values)

    # if the array is empty, postgres requires a type annotation
    if not element.values:
        values_array = sa.cast(values_array, postgresql.ARRAY(sa.String))

    return compiler.process(
        sa.type_coerce(element.json_expr, postgresql.JSONB).has_all(values_array),
        **kwargs,
    )


@compiles(json_has_all_keys, "sqlite")
def _json_has_all_keys_sqlite(element, compiler, **kwargs):
    # "has all keys" is equivalent to "json contains"
    return _json_contains_sqlite_fn(
        left=element.json_expr,
        right=element.values,
        compiler=compiler,
        **kwargs,
    )


def get_dialect(
    obj: Union[str, sa.orm.Session, sa.engine.Engine],
) -> sa.engine.Dialect:
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
    if isinstance(obj, sa.orm.Session):
        url = obj.bind.url
    elif isinstance(obj, sa.engine.Engine):
        url = obj.url
    else:
        url = sa.engine.url.make_url(obj)

    return url.get_dialect()
