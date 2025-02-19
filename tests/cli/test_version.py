import platform
import sqlite3
import sys
from textwrap import dedent
from unittest.mock import Mock

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
from prefect.types._datetime import parse_datetime


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_version_ephemeral_server_type():
    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"], expected_output_contains="Server type:         ephemeral"
        )


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_version_unconfigured_server_type():
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


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_correct_output_ephemeral_sqlite(monkeypatch: pytest.MonkeyPatch):
    version_info = prefect.__version_info__
    assert version_info["date"] is not None, "date is not set"
    built = parse_datetime(version_info["date"])
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
                Git commit:          {version_info["full-revisionid"][:8]}
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


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_correct_output_ephemeral_postgres(monkeypatch: pytest.MonkeyPatch):
    version_info = prefect.__version_info__
    assert version_info["date"] is not None, "date is not set"
    built = parse_datetime(version_info["date"])
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
                Git commit:          {version_info["full-revisionid"][:8]}
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
    assert version_info["date"] is not None, "date is not set"
    built = parse_datetime(version_info["date"])
    profile = prefect.context.get_settings_context().profile

    invoke_and_assert(
        ["version"],
        expected_output=f"""Version:             {prefect.__version__}
API version:         {SERVER_API_VERSION}
Python version:      {platform.python_version()}
Git commit:          {version_info["full-revisionid"][:8]}
Built:               {built.to_day_datetime_string()}
OS/Arch:             {sys.platform}/{platform.machine()}
Profile:             {profile.name}
Server type:         server
Pydantic version:    {pydantic.__version__}
""",
    )
