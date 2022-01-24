from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from prefect.utilities.asyncio import sync_compatible
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.utilities.database import get_dialect

db_interface = provide_database_interface()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

target_metadata = db_interface.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")

    from alembic.script import ScriptDirectory
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: AsyncEngine) -> None:
    """
    Run Alembic migrations using the connection

    Args:
        connection: a database engine
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


@sync_compatible
async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    engine = await db_interface.engine()

    versions_dir = context.get_x_argument(as_dictionary=True).get("versions_dir", None)

    if versions_dir is None:
        # if version dir is not explicitly provided determine versions location from dialect
        dialect = get_dialect(engine=engine)
        if dialect.name == "postgresql":
            versions_dir = Path(context.script.dir / "postgresql")
        elif dialect.name == "sqlite":
            versions_dir = Path(context.script.dir / "sqlite")
        else:
            raise ValueError(f"No versions dir exists for dialect: {dialect.name}")

    context.script.version_locations = [versions_dir]

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
