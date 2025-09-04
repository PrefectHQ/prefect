from __future__ import annotations

import platform
import sqlite3
import sys
from textwrap import dedent
from unittest.mock import AsyncMock, Mock

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

DESIRED_DATE_FORMAT = "%a, %b %d, %Y %I:%M %p"


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_version_ephemeral_server_type():
    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"], expected_output_contains="Server type:          ephemeral"
        )


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_version_unconfigured_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:          unconfigured"
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_version_server_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:          server"
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
            ["version"], expected_output_contains="Server type:          cloud"
        )


@pytest.mark.usefixtures("disable_hosted_api_server")
def test_version_handles_none_metadata_names(monkeypatch: pytest.MonkeyPatch):
    """Test that version command handles packages with None metadata names gracefully."""

    class MockDistribution:
        def __init__(self, metadata: dict[str, str | None], version: str = "1.0.0"):
            self.metadata = metadata
            self.version = version

    mock_distributions = [
        MockDistribution(
            {"Name": "prefect-aws", "Author-email": "help@prefect.io>"}, "2.0.0"
        ),
        MockDistribution({"Name": None, "Author-email": "help@prefect.io>"}),
        MockDistribution({"Author-email": "help@prefect.io>"}),
        MockDistribution(
            {"Name": "some-other-package", "Author-email": "other@example.com"}
        ),
    ]

    def mock_distributions_func():
        return mock_distributions

    monkeypatch.setattr("importlib.metadata.distributions", mock_distributions_func)

    result = invoke_and_assert(
        ["version"],
        expected_code=0,
    )
    assert "prefect-aws" in result.output
    assert "2.0.0" in result.output


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
                Version:              {prefect.__version__}
                API version:          {SERVER_API_VERSION}
                Python version:       {platform.python_version()}
                Git commit:           {version_info["full-revisionid"][:8]}
                Built:                {built.strftime(DESIRED_DATE_FORMAT)}
                OS/Arch:              {sys.platform}/{platform.machine()}
                Profile:              {profile.name}
                Server type:          ephemeral
                Pydantic version:     {pydantic.__version__}
                Server:
                  Database:           sqlite
                  SQLite version:     {sqlite3.sqlite_version}
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
    dialect().name = "postgresql"
    monkeypatch.setattr("prefect.server.utilities.database.get_dialect", dialect)

    mock_result = Mock()
    mock_result.scalar.return_value = "16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)"
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_session
    mock_context_manager.__aexit__.return_value = None
    mock_db = Mock()
    mock_db.session_context.return_value = mock_context_manager

    monkeypatch.setattr(
        "prefect.server.database.dependencies.provide_database_interface",
        lambda: mock_db,
    )

    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        invoke_and_assert(
            ["version"],
            expected_output=dedent(
                f"""
                Version:              {prefect.__version__}
                API version:          {SERVER_API_VERSION}
                Python version:       {platform.python_version()}
                Git commit:           {version_info["full-revisionid"][:8]}
                Built:                {built.strftime(DESIRED_DATE_FORMAT)}
                OS/Arch:              {sys.platform}/{platform.machine()}
                Profile:              {profile.name}
                Server type:          ephemeral
                Pydantic version:     {pydantic.__version__}
                Server:
                  Database:           postgresql
                  PostgreSQL version: 16.9 (Ubuntu 16.9-0ubuntu0.24.04.1)
                """,
            ),
        )
