import uuid
from contextlib import contextmanager
from typing import Generator
from unittest.mock import MagicMock

import httpx
import pytest
from starlette import status

from prefect.client.schemas import Workspace
from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    Profile,
    ProfilesCollection,
    save_profiles,
)
from prefect.testing.cli import invoke_and_assert


def gen_test_workspace(**kwargs) -> Workspace:
    defaults = {
        "account_id": uuid.uuid4(),
        "account_name": "account name",
        "account_handle": "account-handle",
        "workspace_id": uuid.uuid4(),
        "workspace_name": "workspace name",
        "workspace_handle": "workspace-handle",
        "workspace_description": "workspace description",
    }
    defaults.update(kwargs)
    return Workspace(**defaults)


@pytest.fixture
def mock_webbrowser(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.dashboard.webbrowser", mock)
    yield mock


@contextmanager
def _use_profile(profile_name: str) -> Generator[None, None, None]:
    with use_profile(profile_name, include_current_context=False):
        yield


def test_open_current_workspace_in_browser_success(mock_webbrowser, respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active="logged-in-profile",
        )
    )

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )
    with _use_profile("logged-in-profile"):
        invoke_and_assert(
            ["dashboard", "open"],
            expected_code=0,
            expected_output_contains=f"Opened {foo_workspace.handle!r} in browser.",
        )

    mock_webbrowser.open_new_tab.assert_called_with(foo_workspace.ui_url())


@pytest.mark.usefixtures("mock_webbrowser")
@pytest.mark.parametrize("api_url", ["http://localhost:4200", "https://api.prefect.io"])
def test_open_current_workspace_in_browser_failure_no_workspace_set(
    respx_mock, api_url
):
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: api_url,
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active="logged-in-profile",
        )
    )

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[],
        )
    )

    with _use_profile("logged-in-profile"):
        invoke_and_assert(["dashboard", "open"], expected_code=0)


@pytest.mark.usefixtures("mock_webbrowser")
@pytest.mark.parametrize("api_url", ["http://localhost:4200", "https://api.prefect.io"])
def test_open_current_workspace_in_browser_failure_unauthorized(respx_mock, api_url):
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: api_url,
                        PREFECT_API_KEY: "invalid_key",
                    },
                )
            ],
            active="logged-in-profile",
        )
    )

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_401_UNAUTHORIZED,
            json={"detail": "Unauthorized"},
        )
    )

    with _use_profile("logged-in-profile"):
        invoke_and_assert(
            ["dashboard", "open"],
            expected_code=0,
            expected_output_contains=f"Opened {api_url!r} in browser.",
        )
