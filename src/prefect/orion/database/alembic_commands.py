from pathlib import Path

import prefect


def alembic_config():
    from alembic.config import Config

    alembic_dir = Path(prefect.orion.database.__file__).parent
    if not alembic_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {alembic_dir}/alembic.ini")

    alembic_cfg = Config(alembic_dir / "alembic.ini")

    return alembic_cfg


def alembic_upgrade(revision: str = "head", sql: bool = False):
    """
    Run alembic upgrades on Orion database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'head', upgrading all revisions
        sql: run migrations in offline mode and send sql statements to stdout
    """
    # lazy import for performance
    import alembic.command

    alembic.command.upgrade(alembic_config(), revision, sql=sql)


def alembic_downgrade(revision: str = "base", sql: bool = False):
    """
    Run alembic downgrades on Orion database

    Args:
        revision: The revision passed to `alembic downgrade`. Defaults to 'base', downgrading all revisions
        sql: run migrations in offline mode and send sql statements to stdout
    """
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(alembic_config(), revision, sql=sql)


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
