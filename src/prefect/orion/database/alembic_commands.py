from pathlib import Path

import prefect


def alembic_config():
    from alembic.config import Config

    alembic_dir = Path(prefect.orion.database.__file__).parent
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


def alembic_upgrade(n: str = None, sql: bool = False):
    """
    Run alembic upgrades on Orion database

    Args:
        n: The argument to `alembic upgrade`. If not provided, runs all.
        sql: run migrations in offline mode and send sql statements to stdout
    """
    # lazy import for performance
    import alembic.command

    alembic.command.upgrade(alembic_config(), f"{n}" if n else "heads", sql=sql)


def alembic_downgrade(n: str = None, sql: bool = False):
    """
    Run alembic downgrades on Orion database

    Args:
        n: The argument to `alembic downgrade`. If not provided, runs all.
        sql: run migrations in offline mode and send sql statements to stdout
    """
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(alembic_config(), f"{n}" if n else "base", sql=sql)


def alembic_revision(message: str = None, autogenerate: bool = False, **kwargs):
    """
    Create a new revision file for Orion

    Args:
        message: string message to apply to the revision
        autogenerate: whether or not to autogenerate the script from the database
    """
    # lazy import for performance
    import alembic.command

    alembic.command.revision(
        alembic_config(), message=message, autogenerate=autogenerate, **kwargs
    )
