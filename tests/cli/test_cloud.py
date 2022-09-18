import uuid

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


def test_invalid_login(monkeypatch):
    monkeypatch.setattr(
        "prefect.client.cloud.get_cloud_client", get_unauthorized_mock_cloud_client
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "invalid_API_key"],
        expected_code=1,
        expected_output=(
            "Unable to authenticate with Prefect Cloud. Please ensure your credentials are correct."
        ),
    )


def test_login_creates_profile(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)
    monkeypatch.setattr("prefect.cli.cloud.select_workspace", mock_select_workspace)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY],
            user_input="test-profile",
            expected_code=0,
            expected_output_contains=(
                "Logged in to Prefect Cloud using profile 'test-profile'",
                "Workspace is currently set to 'account-1/workspace-1'",
            ),
        )

    profiles = load_profiles()
    assert profiles["test-profile"].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
    }


def test_login_preserves_original_profile(monkeypatch):
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
            user_input="test-profile",
            expected_code=0,
            expected_output_contains=(
                "Logged in to Prefect Cloud using profile 'test-profile'",
                "Workspace is currently set to 'account-1/workspace-1'",
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_DEBUG_MODE: True,
    }


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
