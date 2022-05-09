import uuid

import pytest

import prefect.cli.cloud
from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
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
    "workspace_handle": WORKSPACE_HANDLE
}


class MockCloudClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        pass

    async def read_workspaces(self):
        return [
            WORKSPACE
        ]


def get_mock_cloud_client(*args, **kwargs):
    """Returns a MockCloudClient with hardcoded responses"""
    return MockCloudClient()


def mock_select_workspace(workspaces):
    """Mocks a user selecting a workspace via keyboard input. Will return the first workspace."""
    return list(workspaces)[0]


def test_invalid_login():
    invoke_and_assert(
        ["cloud", "login", "--key", "invalid_API_key"],
        expected_code=1,
        expected_output="Unable to authenticate. Please ensure your credentials are correct."
    )


def test_login_updates_profile(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None))

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY],
            expected_code=0,
            # TODO - why is there a new expected line here?
            expected_output=f"Successfully logged in and set workspace to {FULL_HANDLE!r} in profile \n{cloud_profile!r}."
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: prefect.cli.cloud.build_url_from_workspace(WORKSPACE),
        PREFECT_API_KEY: API_KEY
    }


def test_logout_updates_profile():
    cloud_profile = "cloud-foo"
    save_profiles(ProfilesCollection([Profile(name=cloud_profile, settings={
        PREFECT_API_URL: prefect.cli.cloud.build_url_from_workspace(WORKSPACE),
        PREFECT_API_KEY: API_KEY
    })], active=None))

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=0,
            expected_output=f"Successfully logged out in profile {cloud_profile!r}."
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {}


def test_cannot_logout_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None))

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=1,
            # TODO - random new line here
            expected_output=f"Currently not authenticated in profile {cloud_profile!r}. "
            "Please login with `prefect \ncloud login --key <API_KEY>`."
        )


def test_cannot_set_workspace_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None))

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", f"{FULL_HANDLE}"],
            expected_code=1,
            # TODO - random new line here
            expected_output=f"Currently not authenticated in profile {cloud_profile!r}. "
            "Please login with `prefect \ncloud login --key <API_KEY>`."
        )


def test_set_workspace_updates_profile(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(ProfilesCollection([Profile(name=cloud_profile, settings={
        PREFECT_API_URL: "old workspace",
        PREFECT_API_KEY: API_KEY
    })], active=None))

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set"],
            expected_code=0,
            expected_output=f"Successfully set workspace to {FULL_HANDLE!r} in profile {cloud_profile!r}."
        )
