import platform
import sqlite3
import sys
from textwrap import dedent
from unittest.mock import Mock

import pendulum
import pydantic
import pytest

import prefect
from prefect.client.constants import SERVER_API_VERSION
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


def test_version_ephemeral_server_type(disable_hosted_api_server):
    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"], expected_output_contains="Server type:         ephemeral"
        )


def test_version_unconfigured_server_type(disable_hosted_api_server):
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         unconfigured"
    )


@pytest.mark.usefixtures("use_hosted_api_server")
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


def test_correct_output_ephemeral_sqlite(monkeypatch, disable_hosted_api_server):
    version_info = prefect.__version_info__
    built = pendulum.parse(prefect.__version_info__["date"])
    profile = prefect.context.get_settings_context().profile

    dialect = Mock()
    dialect().name = "sqlite"
    monkeypatch.setattr("prefect.server.utilities.database.get_dialect", dialect)

    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"],
            expected_output=dedent(
                f"""
                Version:             {prefect.__version__}
                API version:         {SERVER_API_VERSION}
                Python version:      {platform.python_version()}
                Git commit:          {version_info['full-revisionid'][:8]}
                Built:               {built.to_day_datetime_string()}
                OS/Arch:             {sys.platform}/{platform.machine()}
                Profile:             {profile.name}
                Server type:         ephemeral
                Pydantic version:    {pydantic.__version__}
                Server:
                  Database:          sqlite
                  SQLite version:    {sqlite3.sqlite_version}
                """,
            ),
        )


def test_correct_output_ephemeral_postgres(monkeypatch, disable_hosted_api_server):
    version_info = prefect.__version_info__
    built = pendulum.parse(prefect.__version_info__["date"])
    profile = prefect.context.get_settings_context().profile

    dialect = Mock()
    dialect().name = "postgres"
    monkeypatch.setattr("prefect.server.utilities.database.get_dialect", dialect)

    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"],
            expected_output=dedent(
                f"""
                Version:             {prefect.__version__}
                API version:         {SERVER_API_VERSION}
                Python version:      {platform.python_version()}
                Git commit:          {version_info['full-revisionid'][:8]}
                Built:               {built.to_day_datetime_string()}
                OS/Arch:             {sys.platform}/{platform.machine()}
                Profile:             {profile.name}
                Server type:         ephemeral
                Pydantic version:    {pydantic.__version__}
                Server:
                  Database:          postgres
                """,
            ),
        )


@pytest.mark.usefixtures("use_hosted_api_server")
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
Pydantic version:    {pydantic.__version__}
""",
    )
