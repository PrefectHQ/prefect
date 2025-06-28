import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import respx
from httpx import Response

from prefect.cli.profile import show_profile_changes
from prefect.client.cloud import CloudUnauthorizedError
from prefect.context import use_profile
from prefect.settings import (
    DEFAULT_PROFILES_PATH,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_DEBUG_MODE,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.settings.profiles import (
    _read_profiles_from,  # type: ignore[reportPrivateUsage]
)
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        yield path


def test_use_profile_unknown_key():
    invoke_and_assert(
        ["profile", "use", "foo"],
        expected_code=1,
        expected_output="Profile 'foo' not found.",
    )


class TestChangingProfileAndCheckingServerConnection:
    @pytest.fixture
    def profiles(self):
        prefect_cloud_api_url = "https://api.prefect.cloud/api"
        prefect_cloud_server_api_url = (
            f"{prefect_cloud_api_url}/accounts/{uuid4()}/workspaces/{uuid4()}"
        )
        hosted_server_api_url = "https://hosted-server.prefect.io/api"

        return ProfilesCollection(
            profiles=[
                Profile(
                    name="prefect-cloud",
                    settings={
                        "PREFECT_API_URL": prefect_cloud_server_api_url,
                        "PREFECT_API_KEY": "a working cloud api key",
                    },
                ),
                Profile(
                    name="prefect-cloud-with-invalid-key",
                    settings={
                        "PREFECT_API_URL": prefect_cloud_server_api_url,
                        "PREFECT_API_KEY": "a broken cloud api key",
                    },
                ),
                Profile(
                    name="hosted-server",
                    settings={
                        "PREFECT_API_URL": hosted_server_api_url,
                    },
                ),
                Profile(
                    name="ephemeral",
                    settings={"PREFECT_SERVER_ALLOW_EPHEMERAL_MODE": True},
                ),
            ],
            active=None,
        )

    @pytest.fixture
    def authorized_cloud(self):
        # attempts to reach the Cloud API implies a good connection
        # to Prefect Cloud as opposed to a hosted Prefect server instance
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            # Mock the health endpoint for cloud
            health = respx_mock.get(
                "https://api.prefect.cloud/api/health",
            ).mock(return_value=Response(200, json={}))

            # Keep the workspaces endpoint mock for backward compatibility
            respx_mock.get(
                "https://api.prefect.cloud/api/me/workspaces",
            ).mock(return_value=Response(200, json=[]))

            yield health

    @pytest.fixture
    def unauthorized_cloud(self):
        # requests to cloud with an invalid key will result in a 401 response
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            # Mock the health endpoint for cloud
            health = respx_mock.get(
                "https://api.prefect.cloud/api/health",
            ).mock(side_effect=CloudUnauthorizedError("Invalid API key"))

            # Keep the workspaces endpoint mock for backward compatibility
            respx_mock.get(
                "https://api.prefect.cloud/api/me/workspaces",
            ).mock(side_effect=CloudUnauthorizedError("Invalid API key"))

            yield health

    @pytest.fixture
    def unhealthy_cloud(self):
        # requests to cloud with an invalid key will result in a 401 response
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            # Mock the health endpoint for cloud with an error
            unhealthy = respx_mock.get(
                "https://api.prefect.cloud/api/health",
            ).mock(side_effect=self.connection_error)

            # Keep the workspaces endpoint mock for backward compatibility
            respx_mock.get(
                "https://api.prefect.cloud/api/me/workspaces",
            ).mock(side_effect=self.connection_error)

            yield unhealthy

    @pytest.fixture
    def hosted_server_has_no_cloud_api(self):
        # if the API URL points to a hosted Prefect server instance, no Cloud API will be found
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            # We don't need to mock the cloud API endpoint anymore since we check server type first
            hosted = respx_mock.get(
                "https://hosted-server.prefect.io/api/me/workspaces",
            ).mock(return_value=Response(404, json={}))

            yield hosted

    @pytest.fixture
    def healthy_hosted_server(self):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            hosted = respx_mock.get(
                "https://hosted-server.prefect.io/api/health",
            ).mock(return_value=Response(200, json={}))

            yield hosted

    def connection_error(self, *args):
        raise Exception

    @pytest.fixture
    def unhealthy_hosted_server(self):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            badly_hosted = respx_mock.get(
                "https://hosted-server.prefect.io/api/health",
            ).mock(side_effect=self.connection_error)

            yield badly_hosted

    @pytest.mark.usefixtures("authorized_cloud")
    def test_authorized_cloud_connection(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "prefect-cloud"],
            expected_output_contains=(
                "Connected to Prefect Cloud using profile 'prefect-cloud'"
            ),
            expected_code=0,
        )

        profiles = load_profiles()
        assert profiles.active_name == "prefect-cloud"

    @pytest.mark.usefixtures("unauthorized_cloud")
    def test_unauthorized_cloud_connection(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "prefect-cloud-with-invalid-key"],
            expected_output_contains=(
                "Error authenticating with Prefect Cloud using profile"
                " 'prefect-cloud-with-invalid-key'"
            ),
            expected_code=1,
        )

        profiles = load_profiles()
        assert profiles.active_name == "prefect-cloud-with-invalid-key"

    @pytest.mark.usefixtures("unhealthy_cloud")
    def test_unhealthy_cloud_connection(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "prefect-cloud"],
            expected_output_contains="Error connecting to Prefect Cloud",
            expected_code=1,
        )

        profiles = load_profiles()
        assert profiles.active_name == "prefect-cloud"

    @pytest.mark.usefixtures("hosted_server_has_no_cloud_api", "healthy_hosted_server")
    def test_using_hosted_server(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "hosted-server"],
            expected_output_contains=(
                "Connected to Prefect server using profile 'hosted-server'"
            ),
            expected_code=0,
        )

        profiles = load_profiles()
        assert profiles.active_name == "hosted-server"

    @pytest.mark.usefixtures(
        "hosted_server_has_no_cloud_api", "unhealthy_hosted_server"
    )
    def test_unhealthy_hosted_server(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "hosted-server"],
            expected_output_contains="Error connecting to Prefect server",
            expected_code=1,
        )

        profiles = load_profiles()
        assert profiles.active_name == "hosted-server"

    def test_using_ephemeral_server(self, profiles: ProfilesCollection):
        save_profiles(profiles)
        invoke_and_assert(
            ["profile", "use", "ephemeral"],
            expected_output_contains=(
                "No Prefect server specified using profile 'ephemeral'"
            ),
            expected_code=0,
        )

        profiles = load_profiles()
        assert profiles.active_name == "ephemeral"


def test_ls_additional_profiles():
    # 'ephemeral' is not the current profile because we have a temporary profile in-use
    # during tests

    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "ls"],
        expected_output_contains=(
            "foo",
            "bar",
        ),
    )


def test_ls_respects_current_from_profile_flag():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["--profile", "foo", "profile", "ls"],
        expected_output_contains=("* foo",),
    )


def test_ls_respects_current_from_context():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    with use_profile("bar"):
        invoke_and_assert(
            ["profile", "ls"],
            expected_output_contains=(
                "foo",
                "* bar",
            ),
        )


def test_create_profile():
    invoke_and_assert(
        ["profile", "create", "foo"],
        expected_output="""
            Created profile with properties:
                name - 'foo'
                from name - None

            Use created profile for future, subsequent commands:
                prefect profile use 'foo'

            Use created profile temporarily for a single command:
                prefect -p 'foo' config view
            """,
    )

    profiles = load_profiles()
    assert profiles["foo"] == Profile(
        name="foo", settings={}, source=PREFECT_PROFILES_PATH.value()
    )


def test_create_profile_from_existing():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "create", "bar", "--from", "foo"],
        expected_output="""
            Created profile with properties:
                name - 'bar'
                from name - foo

            Use created profile for future, subsequent commands:
                prefect profile use 'bar'

            Use created profile temporarily for a single command:
                prefect -p 'bar' config view
            """,
    )

    profiles = load_profiles()
    assert profiles["foo"].settings == {PREFECT_API_KEY: "foo"}, "Foo is unchanged"
    assert profiles["bar"] == Profile(
        name="bar",
        settings={PREFECT_API_KEY: "foo"},
        source=PREFECT_PROFILES_PATH.value(),
    )


def test_create_profile_from_unknown_profile():
    invoke_and_assert(
        ["profile", "create", "bar", "--from", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_create_profile_with_existing_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "create", "foo"],
        expected_output="""
            Profile 'foo' already exists.
            To create a new profile, remove the existing profile first:

                prefect profile delete 'foo'
            """,
        expected_code=1,
    )


def test_create_profile_with_name_conflict_vs_unsaved_default():
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/15643
    """
    invoke_and_assert(
        ["profile", "create", "local"],
        expected_output="""
            Created profile with properties:
                name - 'local'
                from name - None

            Use created profile for future, subsequent commands:
                prefect profile use 'local'

            Use created profile temporarily for a single command:
                prefect -p 'local' config view
            """,
    )


def test_delete_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
                Profile(name="bar", settings={PREFECT_API_KEY: "bar"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "delete", "bar"],
        user_input="y",
        expected_output_contains="Removed profile 'bar'.",
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert "bar" not in profiles


def test_delete_profile_unknown_name():
    invoke_and_assert(
        ["profile", "delete", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_delete_profile_cannot_target_active_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    with use_profile("foo"):
        invoke_and_assert(
            ["profile", "delete", "foo"],
            expected_output=(
                "Profile 'foo' is the active profile. You must switch profiles before"
                " it can be deleted."
            ),
            expected_code=1,
        )


def test_rename_profile_name_exists():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Profile 'bar' already exists.",
        expected_code=1,
    )


def test_rename_profile_unknown_name():
    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_rename_profile_renames_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Renamed profile 'foo' to 'bar'.",
        expected_code=0,
    )

    profiles = load_profiles()
    assert "foo" not in profiles, "The original profile should not exist anymore"
    assert profiles["bar"].settings == {PREFECT_API_KEY: "foo"}, (
        "Settings should be retained"
    )
    assert profiles.active_name != "bar", "The active profile should not be changed"


def test_rename_profile_changes_active_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active="foo",
        )
    )

    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Renamed profile 'foo' to 'bar'.",
        expected_code=0,
    )

    profiles = load_profiles()
    assert profiles.active_name == "bar"


def test_rename_profile_warns_on_environment_variable_active_profile(
    monkeypatch: pytest.MonkeyPatch,
):
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    monkeypatch.setenv("PREFECT_PROFILE", "foo")

    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output_contains=(
            "You have set your current profile to 'foo' with the PREFECT_PROFILE "
            "environment variable. You must update this variable to 'bar' "
            "to continue using the profile."
        ),
        expected_code=0,
    )

    profiles = load_profiles()
    assert profiles.active_name != "foo", (
        "The active profile should not be updated in the file"
    )


def test_inspect_profile_unknown_name():
    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_inspect_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(
                    name="foo",
                    settings={PREFECT_API_KEY: "foo", PREFECT_DEBUG_MODE: True},
                ),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output="""
            PREFECT_API_KEY='foo'
            PREFECT_DEBUG_MODE='True'
            """,
    )


def test_inspect_profile_without_settings():
    save_profiles(
        ProfilesCollection(
            profiles=[Profile(name="foo", settings={})],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output="""
            Profile 'foo' is empty.
            """,
    )


def test_inspect_profile_with_json_output():
    """Test profile inspect command with JSON output flag."""
    import json

    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(
                    name="test-profile",
                    settings={
                        PREFECT_API_URL: "https://test.prefect.cloud/api",
                        PREFECT_DEBUG_MODE: True,
                    },
                )
            ],
            active="test-profile",
        )
    )

    result = invoke_and_assert(
        ["profile", "inspect", "test-profile", "--output", "json"],
        expected_code=0,
    )

    # Parse JSON output and verify it's valid JSON
    output_data = json.loads(result.stdout.strip())

    # Verify key fields are present
    assert "PREFECT_API_URL" in output_data
    assert "PREFECT_DEBUG_MODE" in output_data
    assert output_data["PREFECT_API_URL"] == "https://test.prefect.cloud/api"
    assert (
        output_data["PREFECT_DEBUG_MODE"] == "True"
    )  # Settings are serialized as strings


class TestProfilesPopulateDefaults:
    def test_populate_defaults(self, temporary_profiles_path: Path):
        default_profiles = _read_profiles_from(DEFAULT_PROFILES_PATH)

        assert not temporary_profiles_path.exists()

        invoke_and_assert(
            ["profile", "populate-defaults"],
            user_input="y",
            expected_output_contains=[
                "Proposed Changes:",
                "Add 'ephemeral'",
                "Add 'local'",
                "Add 'cloud'",
                "Add 'test'",
                f"Profiles updated in {temporary_profiles_path}",
                "Use with prefect profile use [PROFILE-NAME]",
            ],
        )

        assert temporary_profiles_path.exists()

        populated_profiles = load_profiles()

        assert populated_profiles.names == default_profiles.names
        assert populated_profiles.active_name == default_profiles.active_name

        assert {"local", "ephemeral", "cloud", "test"} == set(populated_profiles.names)

        for name in default_profiles.names:
            assert populated_profiles[name].settings == default_profiles[name].settings

    def test_populate_defaults_with_existing_profiles(
        self, temporary_profiles_path: Path
    ):
        existing_profiles = ProfilesCollection(
            profiles=[Profile(name="existing", settings={PREFECT_API_KEY: "test_key"})],
            active="existing",
        )
        save_profiles(existing_profiles)

        invoke_and_assert(
            ["profile", "populate-defaults"],
            user_input="y\ny",  # Confirm backup and update
            expected_output_contains=[
                "Proposed Changes:",
                "Add 'ephemeral'",
                "Add 'local'",
                "Add 'cloud'",
                f"Back up existing profiles to {temporary_profiles_path}.bak?",
                f"Update profiles at {temporary_profiles_path}?",
                f"Profiles updated in {temporary_profiles_path}",
            ],
        )

        new_profiles = load_profiles()
        assert {"local", "ephemeral", "cloud", "test", "existing"} == set(
            new_profiles.names
        )

        backup_profiles = _read_profiles_from(
            temporary_profiles_path.with_suffix(".toml.bak")
        )
        assert "existing" in backup_profiles.names
        assert backup_profiles["existing"].settings == {PREFECT_API_KEY: "test_key"}

    def test_populate_defaults_no_changes_needed(self, temporary_profiles_path: Path):
        shutil.copy(DEFAULT_PROFILES_PATH, temporary_profiles_path)

        invoke_and_assert(
            ["profile", "populate-defaults"],
            expected_output_contains=[
                "No changes needed. All profiles are up to date.",
            ],
            expected_code=0,
        )

        assert temporary_profiles_path.read_text() == DEFAULT_PROFILES_PATH.read_text()

    def test_show_profile_changes(self, capsys: pytest.CaptureFixture[str]):
        default_profiles = ProfilesCollection(
            profiles=[
                Profile(
                    name="ephemeral",
                    settings={PREFECT_API_URL: "https://api.prefect.io"},
                ),
                Profile(
                    name="local", settings={PREFECT_API_URL: "http://localhost:4200"}
                ),
                Profile(
                    name="cloud",
                    settings={PREFECT_API_URL: "https://api.prefect.cloud"},
                ),
            ]
        )
        user_profiles = ProfilesCollection(
            profiles=[
                Profile(name="default", settings={PREFECT_API_KEY: "test_key"}),
                Profile(name="custom", settings={PREFECT_API_KEY: "custom_key"}),
            ]
        )

        changes = show_profile_changes(user_profiles, default_profiles)

        assert changes is True

        captured = capsys.readouterr()
        output = captured.out

        assert "Proposed Changes:" in output
        assert "Add 'ephemeral'" in output
        assert "Add 'local'" in output
        assert "Add 'cloud'" in output
