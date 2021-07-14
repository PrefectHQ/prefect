import functools
import inspect
import re
import uuid

import sqlalchemy as sa
from sqlalchemy import Column, create_engine
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import as_declarative, declared_attr, sessionmaker
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import CHAR, TypeDecorator

camel_to_snake = re.compile(r"(?<!^)(?=[A-Z])")

engine = create_engine("sqlite:////tmp/orion.db", echo=True)
Session = sessionmaker(engine, future=True)
GLOBAL_SESSION = Session()


class UUIDDefault(FunctionElement):
    """
    Platform-independent UUID default generator
    """

    name = "uuid_default"


@compiles(UUIDDefault, "postgresql")
def visit_custom_uuid_default_for_postgres(element, compiler, **kwargs):
    return "(GEN_RANDOM_UUID())"


@compiles(UUIDDefault)
def visit_custom_uuid_default(element, compiler, **kwargs):
    return "(hex(randomblob(16)))"


class UUID(TypeDecorator):
    """
    Platform-independent UUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return str(value)


@as_declarative()
class Base(object):
    """
    Base SQLAlchemy model that automatically infers the table name
    and provides ID, created, and updated columns
    """

    @declared_attr
    def __tablename__(cls):
        """
        By default, turn the model's camel-case class name
        into a snake-case table name. Override by providing
        an explicit `__tablename__` class property.
        """
        return camel_to_snake.sub("_", cls.__name__).lower()

    id = Column(
        UUID(),
        primary_key=True,
        server_default=UUIDDefault(),
        default=lambda: str(uuid.uuid4()),
    )
    created = Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated = Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


def provide_session(fn):
    """
    Decorator to provide a session to functions that require it. If a function
    has a parameter annotated as having type `sqlalchemy.orm.Session` that wasn't
    provided, it will be provided automatically.
    """
    fn_parameters = inspect.signature(fn).parameters
    try:
        session_idx, session_name = next(
            (i, k)
            for i, (k, p) in enumerate(fn_parameters.items())
            if p.annotation is sa.orm.Session
        )
    except StopIteration:
        raise ValueError(
            f'Function "{fn.__qualname__}" has no argument '
            "annotated with sqlalchemy.orm.Session."
        )

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        # check if session was provided explicitly or by position
        if session_name in kwargs or session_idx < len(args):
            return fn(*args, **kwargs)
        else:
            # grab session from context (not implemented yet)
            # or use global session if none in context
            session = GLOBAL_SESSION
            kwargs[session_name] = session
            return fn(*args, **kwargs)

    return inner


def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
