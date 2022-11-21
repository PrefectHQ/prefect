import uuid

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


def test_login_with_invalid_key(monkeypatch):
    monkeypatch.setattr(
        "prefect.client.cloud.get_cloud_client", get_unauthorized_mock_cloud_client
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "pcu_foo"],
        expected_code=1,
        expected_output=(
            "Unable to authenticate with Prefect Cloud. It looks like you're using API key from Cloud 1 (https://cloud.prefect.io). Make sure that you generate API key using Cloud 2 (https://app.prefect.cloud)"
        ),
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "pnu_foo"],
        expected_code=1,
        expected_output=(
            "Unable to authenticate with Prefect Cloud. Please ensure your credentials are correct."
        ),
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=1,
        expected_output=(
            "Unable to authenticate with Prefect Cloud. Your key is not in our expected format."
        ),
    )


def test_login_without_workspace_handle(monkeypatch):
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
            expected_output_contains=(
                f"Logged in to Prefect Cloud using profile {cloud_profile!r}.\n"
                f"Workspace is currently set to {FULL_HANDLE!r}. "
                "The workspace can be changed using `prefect cloud workspace set`."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
    }


def test_login_with_workspace_handle(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY, "--workspace", FULL_HANDLE],
            expected_code=0,
            expected_output_contains=(
                f"Logged in to Prefect Cloud using profile {cloud_profile!r}.\n"
                f"Workspace is currently set to {FULL_HANDLE!r}. "
                "The workspace can be changed using `prefect cloud workspace set`."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: FULL_URL,
        PREFECT_API_KEY: API_KEY,
    }


def test_login_with_invalid_workspace_handle(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.get_cloud_client", get_mock_cloud_client)

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "login", "--key", API_KEY, "--workspace", "foo/bar"],
            expected_code=1,
            expected_output_contains="Workspace 'foo/bar' not found.",
        )


def test_logout_current_profile_is_not_logged():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=1,
            expected_output_contains="Current profile is not logged into Prefect Cloud.",
        )


def test_logout_reset_prefect_api_key_and_prefect_api_url():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={PREFECT_API_URL: FULL_URL, PREFECT_API_KEY: API_KEY},
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=0,
            expected_output_contains="Logged out from Prefect Cloud.",
        )

    profiles = load_profiles()
    assert PREFECT_API_URL not in profiles[cloud_profile].settings
    assert PREFECT_API_KEY not in profiles[cloud_profile].settings


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
