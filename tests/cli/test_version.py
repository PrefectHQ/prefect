import platform
import sqlite3
import sys
from unittest.mock import MagicMock, Mock

import pendulum
import pytest

import prefect
from prefect.server.api.server import SERVER_API_VERSION
from prefect.settings import PREFECT_API_URL, PREFECT_CLOUD_API_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert


def test_version_ephemeral_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         ephemeral"
    )


@pytest.mark.usefixtures("use_hosted_orion")
def test_version_server_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         server"
    )


def test_version_cloud_server_type():
    with temporary_settings(
        {
            PREFECT_API_URL: (
                PREFECT_CLOUD_API_URL.value() + "/accounts/<test>/workspaces/<test>"
            )
        }
    ):
        invoke_and_assert(
            ["version"], expected_output_contains="Server type:         cloud"
        )


def test_version_client_error_server_type(monkeypatch):
    monkeypatch.setattr("prefect.get_client", MagicMock(side_effect=ValueError))
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         <client error>"
    )


def test_correct_output_ephemeral_sqlite(monkeypatch):
    version_info = prefect.__version_info__
    built = pendulum.parse(prefect.__version_info__["date"])
    profile = prefect.context.get_settings_context().profile

    dialect = Mock()
    dialect().name = "sqlite"
    monkeypatch.setattr("prefect.server.utilities.database.get_dialect", dialect)

    invoke_and_assert(
        ["version"],
        expected_output=f"""Version:             {prefect.__version__}
API version:         {SERVER_API_VERSION}
Python version:      {platform.python_version()}
Git commit:          {version_info['full-revisionid'][:8]}
Built:               {built.to_day_datetime_string()}
OS/Arch:             {sys.platform}/{platform.machine()}
Profile:             {profile.name}
Server type:         ephemeral
Server:
  Database:          sqlite
  SQLite version:    {sqlite3.sqlite_version}
""",
    )


def test_correct_output_ephemeral_postgres(monkeypatch):
    version_info = prefect.__version_info__
    built = pendulum.parse(prefect.__version_info__["date"])
    profile = prefect.context.get_settings_context().profile

    dialect = Mock()
    dialect().name = "postgres"
    monkeypatch.setattr("prefect.server.utilities.database.get_dialect", dialect)

    invoke_and_assert(
        ["version"],
        expected_output=f"""Version:             {prefect.__version__}
API version:         {SERVER_API_VERSION}
Python version:      {platform.python_version()}
Git commit:          {version_info['full-revisionid'][:8]}
Built:               {built.to_day_datetime_string()}
OS/Arch:             {sys.platform}/{platform.machine()}
Profile:             {profile.name}
Server type:         ephemeral
Server:
  Database:          postgres
""",
    )


@pytest.mark.usefixtures("use_hosted_orion")
def test_correct_output_non_ephemeral_server_type():
    version_info = prefect.__version_info__
    built = pendulum.parse(prefect.__version_info__["date"])
    profile = prefect.context.get_settings_context().profile

    invoke_and_assert(
        ["version"],
        expected_output=f"""Version:             {prefect.__version__}
API version:         {SERVER_API_VERSION}
Python version:      {platform.python_version()}
Git commit:          {version_info['full-revisionid'][:8]}
Built:               {built.to_day_datetime_string()}
OS/Arch:             {sys.platform}/{platform.machine()}
Profile:             {profile.name}
Server type:         server
""",
    )
