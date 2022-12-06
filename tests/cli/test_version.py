from unittest.mock import MagicMock

import pytest

from prefect.settings import PREFECT_API_URL, PREFECT_CLOUD_API_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert


def test_version_ephemeral_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         ephemeral"
    )


@pytest.mark.usefixtures("use_hosted_orion")
def test_version_hosted_server_type():
    invoke_and_assert(
        ["version"], expected_output_contains="Server type:         hosted"
    )


def test_version_cloud_server_type():
    with temporary_settings(
        {
            PREFECT_API_URL: PREFECT_CLOUD_API_URL.value()
            + "/accounts/<test>/workspaces/<test>"
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
