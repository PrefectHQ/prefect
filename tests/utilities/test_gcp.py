import pytest
from unittest.mock import MagicMock

pytest.importorskip("google.cloud")

import prefect
from prefect.utilities.gcp import (
    get_google_client,
    get_storage_client,
    get_bigquery_client,
)


def test_credentials_are_not_required(monkeypatch):
    submodule = MagicMock()
    creds_loader = MagicMock(return_value=MagicMock(project_id="mocked-proj"))
    monkeypatch.setattr("prefect.utilities.gcp.Credentials", creds_loader)

    client = get_google_client(submodule)

    assert not creds_loader.from_service_account_info.called
    assert submodule.Client.call_args[0] == ()
    assert submodule.Client.call_args[1] == dict(project=None)


def test_credentials_are_used(monkeypatch):
    submodule = MagicMock()
    creds_loader = MagicMock()
    creds = MagicMock(project_id="mocked-proj")
    creds_loader.from_service_account_info.return_value = creds
    monkeypatch.setattr("prefect.utilities.gcp.Credentials", creds_loader)
    client = get_google_client(submodule, credentials=dict(x=1))

    assert creds_loader.from_service_account_info.called
    assert submodule.Client.call_args[0] == ()
    assert submodule.Client.call_args[1] == dict(
        credentials=creds, project="mocked-proj"
    )


def test_credentials_are_pulled_from_context(monkeypatch):
    submodule = MagicMock()
    creds_loader = MagicMock()
    creds = MagicMock(project_id="mocked-proj")
    creds_loader.from_service_account_info.return_value = creds
    monkeypatch.setattr("prefect.utilities.gcp.Credentials", creds_loader)
    with prefect.context(secrets=dict(GCP_CREDENTIALS="foobar")):
        client = get_google_client(submodule)

    assert creds_loader.from_service_account_info.called
    assert creds_loader.from_service_account_info.call_args[0][0] == "foobar"
    assert submodule.Client.call_args[0] == ()
    assert submodule.Client.call_args[1] == dict(
        credentials=creds, project="mocked-proj"
    )


def test_provided_project_is_prioritized(monkeypatch):
    submodule = MagicMock()
    creds_loader = MagicMock()
    creds = MagicMock(project_id="mocked-proj")
    creds_loader.from_service_account_info.return_value = creds
    monkeypatch.setattr("prefect.utilities.gcp.Credentials", creds_loader)
    client = get_google_client(submodule, credentials=dict(x=1), project="my-proj")

    assert creds_loader.from_service_account_info.called
    assert submodule.Client.call_args[0] == ()
    assert submodule.Client.call_args[1] == dict(credentials=creds, project="my-proj")
