import uuid

import pytest

import prefect.cli.cloud
from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_DEBUG_MODE,
    Profile,
    ProfilesCollection,
    load_profiles,
    save_profiles,
)
from prefect.testing.cli import invoke_and_assert

ACCOUNT_ID = uuid.uuid4()
ACCOUNT_HANDLE = "account-1"
WORKSPACE_ID = uuid.uuid4()
WORKSPACE_HANDLE = "workspace-1"
API_KEY = "valid_API_key"
FULL_HANDLE = f"{ACCOUNT_HANDLE}/{WORKSPACE_HANDLE}"
WORKSPACE = {
    "account_id": ACCOUNT_ID,
    "account_handle": ACCOUNT_HANDLE,
    "workspace_id": WORKSPACE_ID,
    "workspace_handle": WORKSPACE_HANDLE,
}
FULL_URL = prefect.cli.cloud.build_url_from_workspace(WORKSPACE)


class MockCloudClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        pass

    async def read_workspaces(self):
        return [WORKSPACE]


def get_mock_cloud_client(*args, **kwargs):
    """Returns a MockCloudClient with hardcoded responses"""
    return MockCloudClient()


class MockUnauthorizedCloudClient(MockCloudClient):
    async def read_workspaces(self):
        raise prefect.cli.cloud.CloudUnauthorizedError


def get_unauthorized_mock_cloud_client(*args, **kwargs):
    """Returns a MockUnauthorizedCloudClient that will throw an error"""
    return MockUnauthorizedCloudClient()


def mock_select_workspace(workspaces):
    """
    Mocks a user selecting a workspace via keyboard input.
    Will return the first workspace.
    """
    return list(workspaces)[0]


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_invalid_login(monkeypatch):
    monkeypatch.setattr(
        "prefect.cli.cloud.get_cloud_client", get_unauthorized_mock_cloud_client
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "invalid_API_key"],
        expected_code=1,
        expected_output=(
            "Unable to authenticate. Please ensure your credentials are correct."
        ),
    )


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_login_updates_profile(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY],
            expected_code=0,
            expected_output=(
                f"Successfully logged in and set workspace to {FULL_HANDLE!r} "
                f"in profile {cloud_profile!r}."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
    }


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_login_wont_unset_other_settings(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [Profile(name=cloud_profile, settings={PREFECT_DEBUG_MODE: True})],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY],
            expected_code=0,
            expected_output=(
                f"Successfully logged in and set workspace to {FULL_HANDLE!r} "
                f"in profile {cloud_profile!r}."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
        PREFECT_DEBUG_MODE: True,
    }


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_logout_updates_profile():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={
                        PREFECT_API_URL: FULL_URL,
                        PREFECT_API_KEY: API_KEY,
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=0,
            expected_output=f"Successfully logged out in profile {cloud_profile!r}.",
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {}


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_cannot_logout_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please login with `prefect cloud login --key <API_KEY>`."
            ),
        )


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_cannot_set_workspace_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", f"{FULL_HANDLE}"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please login with `prefect cloud login --key <API_KEY>`."
            ),
        )


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_set_workspace_updates_profile(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={
                        PREFECT_API_URL: "old workspace",
                        PREFECT_API_KEY: API_KEY,
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set"],
            expected_code=0,
            expected_output=(
                f"Successfully set workspace to {FULL_HANDLE!r} "
                f"in profile {cloud_profile!r}."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
    }
