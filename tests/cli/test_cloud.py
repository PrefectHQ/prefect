import sys
import urllib.parse
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
import readchar
from fastapi import status
from typer import Exit

from prefect.cli.cloud import LoginFailed, LoginSuccess
from prefect.client.schemas import Workspace
from prefect.context import get_settings_context, use_profile
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    load_current_profile,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


def gen_test_workspace(**kwargs) -> Workspace:
    kwargs.setdefault("account_id", uuid.uuid4())
    kwargs.setdefault("account_name", "account name")
    kwargs.setdefault("account_handle", "account-handle")
    kwargs.setdefault("workspace_id", uuid.uuid4())
    kwargs.setdefault("workspace_name", "workspace name")
    kwargs.setdefault("workspace_handle", "workspace-handle")
    kwargs.setdefault("workspace_description", "workspace description")
    return Workspace(**kwargs)


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.cloud.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@pytest.fixture(autouse=True)
def restore_logging_setup():
    yield
    # Uvicorn is a maniac and will set logging to their configuration on startup
    setup_logging(incremental=False)


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        # Ensure the test profile is persisted already to simplify assertions
        save_profiles(
            profiles=ProfilesCollection(profiles=[get_settings_context().profile])
        )
        yield path


@pytest.fixture
def mock_webbrowser(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.cloud.webbrowser", mock)
    yield mock


@pytest.mark.parametrize(
    "key,expected_output",
    [
        (
            "pcu_foo",
            "Unable to authenticate with Prefect Cloud. It looks like you're using API key from Cloud 1 (https://cloud.prefect.io). Make sure that you generate API key using Cloud 2 (https://app.prefect.cloud)",
        ),
        (
            "pnu_foo",
            "Unable to authenticate with Prefect Cloud. Please ensure your credentials are correct.",
        ),
        (
            "foo",
            "Unable to authenticate with Prefect Cloud. Your key is not in our expected format.",
        ),
    ],
)
def test_login_with_invalid_key(key, expected_output, respx_mock):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_403_FORBIDDEN)
    )
    invoke_and_assert(
        ["cloud", "login", "--key", key, "--workspace", "foo"],
        expected_code=1,
        expected_output=expected_output,
    )


def test_login_with_key_and_missing_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "apple/berry"],
        expected_code=1,
        expected_output="Workspace 'apple/berry' not found. Available workspaces: 'test/foo', 'test/bar'",
    )


def test_login_with_key_and_no_workspaces(respx_mock):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_200_OK, json=[])
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "bar"],
        expected_code=1,
        expected_output="Workspace 'bar' not found.",
    )


def test_login_with_key_and_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "test/foo"],
        expected_code=0,
        expected_output="Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.parametrize("args", [[], ["--workspace", "test/foo"], ["--key", "key"]])
def test_login_with_non_interactive_missing_args(args):
    invoke_and_assert(
        ["cloud", "login", *args],
        expected_code=1,
        expected_output="When not using an interactive terminal, you must supply a `--key` and `--workspace`.",
    )


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_select_first_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=0,
        user_input=readchar.key.ENTER,
        expected_output_contains=[
            "? Which workspace would you like to use?",
            "test/foo",
            "test/bar",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_select_second_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=0,
        user_input=readchar.key.DOWN + readchar.key.ENTER,
        expected_output_contains=[
            "? Which workspace would you like to use?",
            "test/foo",
            "test/bar",
            "Authenticated with Prefect Cloud! Using workspace 'test/bar'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_interactive_key_single_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=readchar.key.DOWN + readchar.key.ENTER + "foo" + readchar.key.ENTER,
        expected_output_contains=[
            "? How would you like to authenticate? [Use arrows to move; enter to select]",
            "Log in with a web browser",
            "Paste an API key",
            "Paste your API key:",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_interactive_key_multiple_workspaces(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Select paste a key
            readchar.key.DOWN
            + readchar.key.ENTER
            # Send a key
            + "foo"
            + readchar.key.ENTER
            # Select the second workspace
            + readchar.key.DOWN
            + readchar.key.ENTER
        ),
        expected_output_contains=[
            "? How would you like to authenticate? [Use arrows to move; enter to select]",
            "Log in with a web browser",
            "Paste an API key",
            "Paste your API key:",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_browser_single_workspace(respx_mock, mock_webbrowser):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    def post_success(ui_url):
        # Parse the callback url that the UI would send a response to
        callback = urllib.parse.unquote(
            urllib.parse.urlparse(ui_url).query.split("=")[1]
        )
        # Bypass the mocks
        respx_mock.route(url__startswith=callback).pass_through()
        httpx.post(callback + "/success", content=LoginSuccess(api_key="foo").json())

    mock_webbrowser.open_new_tab.side_effect = post_success

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Select with browser
            readchar.key.ENTER
        ),
        expected_output_contains=[
            "? How would you like to authenticate? [Use arrows to move; enter to select]",
            "Log in with a web browser",
            "Paste an API key",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_browser_failure_in_browser(respx_mock, mock_webbrowser):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    def post_failure(ui_url):
        # Parse the callback url that the UI would send a response to
        callback = urllib.parse.unquote(
            urllib.parse.urlparse(ui_url).query.split("=")[1]
        )
        # Bypass the mocks
        respx_mock.route(url__startswith=callback).pass_through()
        httpx.post(callback + "/failure", content=LoginFailed(reason="Oh no!").json())

    mock_webbrowser.open_new_tab.side_effect = post_failure

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=1,
        user_input=(
            # Select with browser
            readchar.key.ENTER
        ),
        expected_output_contains=[
            "? How would you like to authenticate? [Use arrows to move; enter to select]",
            "Log in with a web browser",
            "Paste an API key",
            "Failed to log in. Oh no!",
        ],
    )

    settings = load_current_profile().settings
    assert PREFECT_API_KEY not in settings
    assert PREFECT_API_URL not in settings


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_no_reauth(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

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
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input="n" + readchar.key.ENTER,
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                "Using the existing authentication on this profile.",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_no_reauth_new_workspace(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

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
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # No, do not reuath
                "n"
                + readchar.key.ENTER
                # Yes, switch workspaces
                + "y"
                + readchar.key.ENTER
                # Select 'bar'
                + readchar.key.DOWN
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                "Using the existing authentication on this profile.",
                "? Which workspace would you like to use? [Use arrows to move; enter to select]",
                "Authenticated with Prefect Cloud! Using workspace 'test/bar'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_yes_reauth(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

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
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # Yes, reauth
                "y"
                + readchar.key.ENTER
                # Enter key manually
                + readchar.key.DOWN
                + readchar.key.ENTER
                # Enter new key
                + "bar"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                "? How would you like to authenticate? [Use arrows to move; enter to select]",
                "Log in with a web browser",
                "Paste an API key",
                "Paste your API key:",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "bar"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_with_invalid_api_url_prompts_workspace_change(
    respx_mock,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: "oh-no",
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # Yes, reauth
                "y"
                + readchar.key.ENTER
                # Enter a key
                + readchar.key.DOWN
                + readchar.key.ENTER
                + "bar"
                + readchar.key.ENTER
                # Select the first workspace
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "It looks like you're already authenticated on this profile.",
                "? Which workspace would you like to use?",
                "test/foo",
                "test/bar",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "bar"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_another_profile(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    current_profile = load_current_profile()

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                ),
                current_profile,
            ],
            active=current_profile.name,
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # No, do not reauth
            "n"
            + readchar.key.ENTER
            # Yes, switch profiles
            + "y"
            + readchar.key.ENTER
            # Use the first profile
            + readchar.key.ENTER
        ),
        expected_output_contains=[
            "? Would you like to switch to an authenticated profile? [Y/n]:",
            "? Which authenticated profile would you like to switch to?",
            "logged-in-profile",
            "Switched to authenticated profile 'logged-in-profile'.",
        ],
    )

    profiles = load_profiles()
    assert profiles.active_name == "logged-in-profile"
    settings = profiles.active_profile.settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()

    # Current is the test profile active in the context
    previous_profile = load_current_profile()
    assert PREFECT_API_KEY not in previous_profile.settings


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_another_profile_cancel_during_select(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    current_profile = load_current_profile()

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                ),
                current_profile,
            ],
            active=current_profile.name,
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=1,
        user_input=(
            # No, do not reauth
            "n"
            + readchar.key.ENTER
            # Yes, switch profiles
            + "y"
            + readchar.key.ENTER
            # Abort!
            + readchar.key.CTRL_C
        ),
        expected_output_contains=[
            "? Would you like to switch to an authenticated profile? [Y/n]:",
            "? Which authenticated profile would you like to switch to?",
            "logged-in-profile",
            "Aborted",
        ],
    )

    current_profile = load_current_profile()
    profiles = load_profiles()

    # The active profile should not have changed
    assert profiles.active_name != "logged-in-profile"
    assert profiles.active_name == current_profile.name

    # The current profile settings are not mutated
    settings = current_profile.settings
    assert PREFECT_API_KEY not in settings
    assert PREFECT_API_URL not in settings

    # Other profile should not be updated
    assert PREFECT_API_KEY not in settings


def test_logout_current_profile_is_not_logged_in():
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
                    settings={PREFECT_API_URL: "foo", PREFECT_API_KEY: "bar"},
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

        settings = load_current_profile()

    assert PREFECT_API_URL not in settings
    assert PREFECT_API_KEY not in settings


def test_cannot_set_workspace_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", "foo/bar"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_set_workspace_updates_profile(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.dict(json_compatible=True),
                bar_workspace.dict(json_compatible=True),
            ],
        )
    )

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "fake-key",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", bar_workspace.handle],
            expected_code=0,
            expected_output=(
                f"Successfully set workspace to {bar_workspace.handle!r} "
                f"in profile {cloud_profile!r}."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: bar_workspace.api_url(),
        PREFECT_API_KEY: "fake-key",
    }
