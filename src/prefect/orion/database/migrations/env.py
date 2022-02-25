# Originally generated from `alembic init`
# https://alembic.sqlalchemy.org/en/latest/tutorial.html#creating-an-environment

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from prefect.orion.database.dependencies import provide_database_interface
from prefect.utilities.asyncio import sync_compatible

db_interface = provide_database_interface()
config = context.config
target_metadata = db_interface.Base.metadata


def dry_run_migrations() -> None:
    """
    Perform a dry run of migrations.

    This will create the sql statements without actually running them against the
    database and output them to stdout.
    """
    url = db_interface.database_config.connection_url
    context.script.version_locations = [db_interface.orm.versions_dir]

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: AsyncEngine) -> None:
    """
    Run Alembic migrations using the connection.

    Args:
        connection: a database engine.
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


@sync_compatible
async def apply_migrations() -> None:
    """
    Apply migrations to the database.
    """
    engine = await db_interface.engine()
    context.script.version_locations = [db_interface.orm.versions_dir]

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)


if context.is_offline_mode():
    dry_run_migrations()
else:
    apply_migrations()
