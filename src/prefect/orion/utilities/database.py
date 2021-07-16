import re
import uuid

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import as_declarative, declared_attr, sessionmaker
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import CHAR, TypeDecorator

camel_to_snake = re.compile(r"(?<!^)(?=[A-Z])")

engine = create_async_engine("sqlite+aiosqlite:////tmp/orion.db", echo=True)
OrionAsyncSession = sessionmaker(
    engine, future=True, expire_on_commit=False, class_=AsyncSession
)


class UUIDDefault(FunctionElement):
    """
    Platform-independent UUID default generator.
    Note the actual functionality for this class is speficied in the
    `compiles`-decorated functions below
    """

    name = "uuid_default"


@compiles(UUIDDefault, "postgresql")
def visit_custom_uuid_default_for_postgres(element, compiler, **kwargs):
    """
    Generates a random UUID in Postgres; requires the pgcrypto extension.
    """

    return "(GEN_RANDOM_UUID())"


@compiles(UUIDDefault)
def visit_custom_uuid_default(element, compiler, **kwargs):
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


async def reset_db(engine=engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
