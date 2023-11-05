import sys
import urllib.parse
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
import readchar
from starlette import status
from typer import Exit

from prefect.cli.cloud import LoginFailed, LoginSuccess
from prefect.client.schemas import Workspace
from prefect.context import get_settings_context, use_profile
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_CLOUD_UI_URL,
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
            (
                "Unable to authenticate with Prefect Cloud. It looks like you're using"
                " API key from Cloud 1 (https://cloud.prefect.io). Make sure that you"
                " generate API key using Cloud 2 (https://app.prefect.cloud)"
            ),
        ),
        (
            "pnu_foo",
            (
                "Unable to authenticate with Prefect Cloud. Please ensure your"
                " credentials are correct and unexpired."
            ),
        ),
        (
            "foo",
            (
                "Unable to authenticate with Prefect Cloud. Your key is not in our"
                " expected format: 'pnu_' or 'pnb_'."
            ),
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


@pytest.mark.parametrize(
    "key",
    [
        "pnu_foo",
        "foo",
    ],
)
def test_login_with_prefect_api_key_env_var_different_than_key_exits_with_error(key):
    with temporary_settings({PREFECT_API_KEY: "pnu_baz"}):
        invoke_and_assert(
            ["cloud", "login", "--key", key, "--workspace", "foo"],
            expected_code=1,
            expected_output=(
                "Cannot log in with a key when a different PREFECT_API_KEY is present"
                " as an environment variable that will override it."
            ),
        )


@pytest.mark.parametrize(
    "env_var_api_key,key,expected_output",
    [
        (
            "pnu_foo",
            "pnu_foo",
            (
                "Unable to authenticate with Prefect Cloud. Please ensure your"
                " credentials are correct and unexpired."
            ),
        ),
        (
            "foo",
            "foo",
            (
                "Unable to authenticate with Prefect Cloud. Your key is not in our"
                " expected format."
            ),
        ),
    ],
)
def test_login_with_prefect_api_key_env_var_equal_to_invalid_key_exits_with_error(
    key, expected_output, env_var_api_key, respx_mock
):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_403_FORBIDDEN)
    )
    with temporary_settings({PREFECT_API_KEY: env_var_api_key}):
        invoke_and_assert(
            ["cloud", "login", "--key", key, "--workspace", "test/foo"],
            expected_code=1,
            expected_output=(expected_output),
        )


def test_login_with_prefect_api_key_env_var_equal_to_valid_key_succeeds(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.dict(json_compatible=True)],
        )
    )

    with temporary_settings({PREFECT_API_KEY: "pnu_foo"}):
        invoke_and_assert(
            ["cloud", "login", "--key", "pnu_foo", "--workspace", "test/foo"],
            expected_code=0,
            expected_output=(
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'."
            ),
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
        expected_output=(
            "Workspace 'apple/berry' not found. Available workspaces: 'test/foo',"
            " 'test/bar'"
        ),
    )


def test_login_with_key_and_workspace_with_no_workspaces(respx_mock):
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
        expected_output=(
            "When not using an interactive terminal, you must supply a `--key` and"
            " `--workspace`."
        ),
    )


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_no_workspaces(respx_mock):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=1,
        user_input=readchar.key.ENTER,
        expected_output_contains=[
            "No workspaces found! Create a workspace at"
            f" {PREFECT_CLOUD_UI_URL.value()} and try again."
        ],
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
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
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
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
            "Log in with a web browser",
            "Paste an API key",
            "Paste your API key:",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
@pytest.mark.flaky(max_runs=2)
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
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
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
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
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
                (
                    "? Which workspace would you like to use? [Use arrows to move;"
                    " enter to select]"
                ),
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
                (
                    "? How would you like to authenticate? [Use arrows to move; enter"
                    " to select]"
                ),
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
            expected_output_contains=(
                "Current profile is not logged into Prefect Cloud."
            ),
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


def test_cannot_get_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "get", str(uuid.uuid4())],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_get_webhook_by_id(respx_mock):
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
            active=None,
        )
    )

    webhook_id = str(uuid.uuid4())
    webhook = {
        "id": webhook_id,
        "name": "foobar",
        "enabled": True,
        "template": (
            '{ "event": "your.event.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
        ),
        "slug": "your-webhook-slug",
    }

    respx_mock.get(f"{foo_workspace.api_url()}/webhooks/{webhook_id}").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=webhook,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "get", webhook_id],
            expected_code=0,
            expected_output_contains=[webhook["name"]],
        )


def test_cannot_list_webhooks_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "ls"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_list_webhooks(respx_mock):
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
            active=None,
        )
    )

    webhook1 = {
        "id": str(uuid.uuid4()),
        "name": "foobar",
        "enabled": True,
        "template": (
            '{ "event": "your.event.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
        ),
        "slug": "your-webhook-slug",
    }
    webhook2 = {
        "id": str(uuid.uuid4()),
        "name": "bazzbuzz",
        "enabled": True,
        "template": (
            '{ "event": "your.event2.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
        ),
        "slug": "your-webhook2-slug",
    }

    respx_mock.post(f"{foo_workspace.api_url()}/webhooks/filter").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[webhook1, webhook2],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "ls"],
            expected_code=0,
            expected_output_contains=[webhook1["name"], webhook2["name"]],
        )


def test_cannot_create_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "create", "foobar-webhook", "-t", "some-template"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_cannot_create_webhook_without_template():
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
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "create", "foobar-webhook"],
            expected_code=1,
            expected_output_contains=(
                "Please provide a Jinja2 template expression in the --template flag"
            ),
        )


def test_create_webhook(respx_mock):
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
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        webhook_to_create = {
            "name": "whoopity-whoop-webhook",
            "description": "we be webhookin'",
            "template": "{}",
        }
        respx_mock.post(
            f"{foo_workspace.api_url()}/webhooks/", json=webhook_to_create
        ).mock(
            return_value=httpx.Response(
                status.HTTP_201_CREATED,
                json=webhook_to_create,
            )
        )
        invoke_and_assert(
            [
                "cloud",
                "webhook",
                "create",
                webhook_to_create["name"],
                "-t",
                webhook_to_create["template"],
                "-d",
                webhook_to_create["description"],
            ],
            expected_code=0,
            expected_output=f"Successfully created webhook {webhook_to_create['name']}",
        )


def test_cannot_rotate_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "rotate", str(uuid.uuid4())],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_rotate_webhook(respx_mock):
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
            active=None,
        )
    )
    webhook_id = str(uuid.uuid4())
    webhook_slug = "webhook-slug-1234"

    respx_mock.post(f"{foo_workspace.api_url()}/webhooks/{webhook_id}/rotate").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"slug": webhook_slug},
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "rotate", webhook_id],
            expected_code=0,
            user_input="y" + readchar.key.ENTER,
            expected_output_contains=(
                f"Successfully rotated webhook URL to {webhook_slug}"
            ),
        )


def test_cannot_toggle_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "toggle", str(uuid.uuid4())],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_toggle_webhook(respx_mock):
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
            active=None,
        )
    )
    webhook_id = str(uuid.uuid4())

    respx_mock.get(f"{foo_workspace.api_url()}/webhooks/{webhook_id}").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"enabled": True},
        )
    )

    respx_mock.patch(
        f"{foo_workspace.api_url()}/webhooks/{webhook_id}", json={"enabled": False}
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "toggle", webhook_id],
            expected_code=0,
            expected_output_contains="Webhook is now disabled",
        )


def test_cannot_update_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "update", str(uuid.uuid4())],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_update_webhook(respx_mock):
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
            active=None,
        )
    )

    webhook_id = str(uuid.uuid4())
    new_webhook_name = "wowza-webhooks"
    existing_webhook = {
        "name": "this will change",
        "description": "this won't change",
        "template": "neither will this",
    }
    respx_mock.get(f"{foo_workspace.api_url()}/webhooks/{webhook_id}").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=existing_webhook,
        )
    )

    request_body = {
        **existing_webhook,
        "name": new_webhook_name,
    }
    respx_mock.put(
        f"{foo_workspace.api_url()}/webhooks/{webhook_id}", json=request_body
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "update", webhook_id, "--name", new_webhook_name],
            expected_code=0,
            expected_output=f"Successfully updated webhook {webhook_id}",
        )


def test_cannot_delete_webhook_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "webhook", "delete", str(uuid.uuid4())],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_delete_webhook(respx_mock):
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
            active=None,
        )
    )
    webhook_id = str(uuid.uuid4())

    respx_mock.delete(f"{foo_workspace.api_url()}/webhooks/{webhook_id}").mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "webhook", "delete", webhook_id],
            expected_code=0,
            user_input="y" + readchar.key.ENTER,
            expected_output_contains=f"Successfully deleted webhook {webhook_id}",
        )


def test_webhook_methods_with_invalid_uuid():
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
            active=None,
        )
    )
    bad_webhook_id = "invalid_uuid"

    with use_profile("logged-in-profile"):
        for cmd in ["delete", "toggle", "update", "rotate", "get"]:
            invoke_and_assert(
                ["cloud", "webhook", cmd, bad_webhook_id],
                expected_code=2,
            )
