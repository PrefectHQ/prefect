from unittest import mock

from prefect.orion.database.alembic_commands import (
    alembic_upgrade,
    alembic_downgrade,
    alembic_revision,
)

# These tests do not test the actual migration functionality, only that the commands are wrapped and called


class TestAlembicCommands:
    @mock.patch("alembic.command.upgrade")
    def test_alembic_upgrade_defaults(self, mocked):
        alembic_upgrade()
        args, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert args[1] == "head"
        assert kwargs["sql"] is False

    @mock.patch("alembic.command.upgrade")
    def test_alembic_upgrade_passed_params(self, mocked):
        alembic_upgrade("revision123", sql=True)
        args, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert args[1] == "revision123"
        assert kwargs["sql"] is True

    @mock.patch("alembic.command.downgrade")
    def test_alembic_downgrade_defaults(self, mocked):
        alembic_downgrade()
        args, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert args[1] == "base"
        assert kwargs["sql"] is False

    @mock.patch("alembic.command.downgrade")
    def test_alembic_downgrade_passed_params(self, mocked):
        alembic_downgrade("revision123", sql=True)
        args, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert args[1] == "revision123"
        assert kwargs["sql"] is True

    @mock.patch("alembic.command.revision")
    def test_alembic_revision_defaults(self, mocked):
        alembic_revision()
        _, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert kwargs["message"] is None
        assert kwargs["autogenerate"] is False

    @mock.patch("alembic.command.revision")
    def test_alembic_revision_passed_params(self, mocked):
        alembic_revision(message="new_revision", autogenerate=True)
        _, kwargs = mocked.call_args
        assert mocked.call_count == 1
        assert kwargs["message"] == "new_revision"
        assert kwargs["autogenerate"] is True
