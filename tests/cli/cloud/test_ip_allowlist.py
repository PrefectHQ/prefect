import ipaddress
from datetime import datetime
from typing import Optional

import httpx
import pytest
from tests.cli.cloud.test_cloud import gen_test_workspace

from prefect._internal.compatibility.starlette import status
from prefect.client.schemas.objects import IPAllowlist, IPAllowlistEntry
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

SAMPLE_ALLOWLIST = IPAllowlist(
    entries=[
        IPAllowlistEntry(
            ip_network="192.168.1.1",  # type: ignore
            enabled=True,
            description="Perimeter81 Gateway",
            last_seen=str(datetime(2024, 8, 13, 16)),
        ),
        IPAllowlistEntry(
            ip_network="192.168.1.0/24",  # type: ignore
            enabled=True,
            description="CIDR block for 192.168.0.0 to 192.168.1.255",
        ),
        IPAllowlistEntry(
            ip_network="2001:0db8:85a3:0000:0000:8a2e:0370:7334",  # type: ignore
            enabled=False,
            description="An IPv6 address",
        ),
        IPAllowlistEntry(
            ip_network="2001:0db8:85a3::/64",  # type: ignore
            enabled=True,
            description="An IPv6 CIDR block",
        ),
    ]
)


@pytest.fixture
def workspace_with_logged_in_profile():
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    profile_name = "logged-in-profile"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=profile_name,
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    return foo_workspace, profile_name


@pytest.fixture
def account_with_ip_allowlisting_enabled(respx_mock, workspace_with_logged_in_profile):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            # presence of the setting key means account has access to it. enable/disable toggles the value
            json={"enforce_ip_allowlist": True},
        )
    )

    return workspace, profile


def test_ip_allowlist_requires_access_to_ip_allowlisting(
    respx_mock, workspace_with_logged_in_profile
):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            # absence of the setting key means account does not have access to it
            json={},
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "enable"],
            expected_code=1,
            expected_output_contains="IP allowlisting is not available for this account",
        )


def test_ip_allowlist_enable(respx_mock, workspace_with_logged_in_profile):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"enforce_ip_allowlist": False},
        )
    )
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist/my_access"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"allowed": True, "detail": "You're in."},
        )
    )

    respx_mock.patch(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings",
        json={"enforce_ip_allowlist": True},
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "enable"],
            expected_code=0,
            user_input="y",
            expected_output_contains="IP allowlist enabled",
        )


def test_ip_allowlist_enable_already_enabled(
    respx_mock, workspace_with_logged_in_profile
):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"enforce_ip_allowlist": True},
        )
    )

    # should not make the PATCH request to enable it

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "enable"],
            expected_code=0,
            expected_output_contains="IP allowlist is already enabled",
        )


def test_ip_allowlist_enable_aborts_if_would_block_current_user(
    respx_mock, workspace_with_logged_in_profile
):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"enforce_ip_allowlist": False},
        )
    )
    respx_mock.get(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist/my_access"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"allowed": False, "detail": "You're not in."},
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "enable"],
            expected_code=1,
            expected_output_contains="Error enabling IP allowlist: You're not in.",
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_disable(respx_mock, workspace_with_logged_in_profile):
    workspace, profile = workspace_with_logged_in_profile
    respx_mock.patch(
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/settings",
        json={"enforce_ip_allowlist": False},
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "disable"],
            expected_code=0,
            expected_output_contains="IP allowlist disabled",
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_ls(respx_mock, workspace_with_logged_in_profile):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=SAMPLE_ALLOWLIST.model_dump(mode="json"),
        )
    )

    every_expected_entry_ip = [
        str(entry.ip_network) for entry in SAMPLE_ALLOWLIST.entries
    ]

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "ls"],
            expected_code=0,
            expected_output_contains=every_expected_entry_ip,
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_ls_empty_list(respx_mock, workspace_with_logged_in_profile):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json={"entries": []},
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "ls"],
            expected_code=0,
            expected_output_contains="IP allowlist is empty. Add an entry",
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
@pytest.mark.parametrize("description", [None, "some short description"])
def test_ip_allowlist_add(
    description: Optional[str], workspace_with_logged_in_profile, respx_mock
):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=SAMPLE_ALLOWLIST.model_dump(mode="json"),
        )
    )
    expected_update_request = IPAllowlist(
        entries=SAMPLE_ALLOWLIST.entries
        + [
            IPAllowlistEntry(
                ip_network="192.188.1.5",
                enabled=True,
                description=description,  # type: ignore
            )
        ]
    )
    mocked_put_request = respx_mock.put(
        url, json=expected_update_request.model_dump(mode="json")
    ).mock(return_value=httpx.Response(status.HTTP_204_NO_CONTENT))

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "add", "192.188.1.5"]
            + (["-d", description] if description else []),
            expected_code=0,
        )

    assert mocked_put_request.called


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_add_invalid_ip(workspace_with_logged_in_profile, respx_mock):
    _, profile = workspace_with_logged_in_profile
    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "add", "258.235.432.234"],
            expected_code=2,
            expected_output_contains="Invalid value for 'IP address or range'",
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_add_existing_ip_entry(
    workspace_with_logged_in_profile, respx_mock
):
    allowlist = IPAllowlist(
        entries=[
            IPAllowlistEntry(
                ip_network="192.168.1.1",  # type: ignore
                enabled=True,
                description="original description",
            )
        ]
    )
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK, json=allowlist.model_dump(mode="json")
        )
    )
    expected_update_request = allowlist.model_dump(mode="json")
    expected_update_request["entries"][0]["description"] = "updated description"
    mocked_put_request = respx_mock.put(url, json=expected_update_request).mock(
        return_value=httpx.Response(status.HTTP_204_NO_CONTENT)
    )

    with use_profile(profile):
        invoke_and_assert(
            [
                "cloud",
                "ip-allowlist",
                "add",
                str(SAMPLE_ALLOWLIST.entries[0].ip_network),
                "-d",
                "updated description",
            ],
            user_input="y",
            expected_code=0,
        )

    assert mocked_put_request.called


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_remove(workspace_with_logged_in_profile, respx_mock):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=SAMPLE_ALLOWLIST.model_dump(mode="json"),
        )
    )

    entry_to_remove = SAMPLE_ALLOWLIST.entries[0]
    expected_update_request = IPAllowlist(
        entries=[
            entry
            for entry in SAMPLE_ALLOWLIST.entries
            if entry.ip_network != entry_to_remove.ip_network
        ]
    )
    mocked_put_request = respx_mock.put(
        url, json=expected_update_request.model_dump(mode="json")
    ).mock(return_value=httpx.Response(status.HTTP_204_NO_CONTENT))

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "remove", str(entry_to_remove.ip_network)],
            expected_code=0,
        )

    assert mocked_put_request.called


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_handles_422_on_removal_of_own_ip_address(
    workspace_with_logged_in_profile, respx_mock
):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    my_ip_entry = IPAllowlistEntry(
        ip_network="127.0.0.1",  # type: ignore
        enabled=True,
        description="My IP - cannot remove",
    )
    allowlist = IPAllowlist(
        entries=[
            my_ip_entry,
            IPAllowlistEntry(
                ip_network="192.168.1.0/24",  # type: ignore
                enabled=True,
                description="CIDR block for 192.168.0.0 to 192.168.1.255",
            ),
        ]
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=allowlist.model_dump(mode="json"),
        )
    )

    allowlist.entries.remove(my_ip_entry)
    expected_server_error = "Your current IP address (127.0.0.1) must be included in the IP allowlist to prevent account lockout."
    respx_mock.put(url, json=allowlist.model_dump(mode="json")).mock(
        return_value=httpx.Response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            json={"detail": expected_server_error},
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "remove", "127.0.0.1"],
            expected_code=1,
            expected_output_contains=expected_server_error,
            expected_line_count=1,
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_toggle(workspace_with_logged_in_profile, respx_mock):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=SAMPLE_ALLOWLIST.model_dump(mode="json"),
        )
    )

    entry_to_toggle = SAMPLE_ALLOWLIST.entries[0]
    expected_update_request = IPAllowlist(
        entries=[
            IPAllowlistEntry(
                ip_network=entry.ip_network,
                enabled=not entry.enabled,
                description=entry.description,
                last_seen=entry.last_seen,
            )
            if entry.ip_network == entry_to_toggle.ip_network
            else entry
            for entry in SAMPLE_ALLOWLIST.entries
        ]
    )
    mocked_put_request = respx_mock.put(
        url, json=expected_update_request.model_dump(mode="json")
    ).mock(return_value=httpx.Response(status.HTTP_204_NO_CONTENT))

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "toggle", str(entry_to_toggle.ip_network)],
            expected_code=0,
        )

    assert mocked_put_request.called


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_toggle_nonexistent_entry(
    workspace_with_logged_in_profile, respx_mock
):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=SAMPLE_ALLOWLIST.model_dump(mode="json"),
        )
    )

    nonexistent_ip = "192.168.0.1"
    assert not any(
        entry.ip_network == ipaddress.ip_network(nonexistent_ip)
        for entry in SAMPLE_ALLOWLIST.entries
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "toggle", nonexistent_ip],
            expected_code=1,
            expected_output_contains=f"No entry found with IP address `{nonexistent_ip}`",
        )


@pytest.mark.usefixtures("account_with_ip_allowlisting_enabled")
def test_ip_allowlist_toggle_handles_422_on_disable_of_own_ip_address(
    workspace_with_logged_in_profile, respx_mock
):
    workspace, profile = workspace_with_logged_in_profile
    url = (
        f"{PREFECT_CLOUD_API_URL.value()}/accounts/{workspace.account_id}/ip_allowlist"
    )
    my_ip_entry = IPAllowlistEntry(
        ip_network="127.0.0.1",  # type: ignore
        enabled=True,
        description="My IP - cannot remove",
    )
    allowlist = IPAllowlist(
        entries=[
            my_ip_entry,
            IPAllowlistEntry(
                ip_network="192.168.1.0/24",  # type: ignore
                enabled=True,
                description="CIDR block for 192.168.0.0 to 192.168.1.255",
            ),
        ]
    )
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=allowlist.model_dump(mode="json"),
        )
    )

    my_ip_entry.enabled = False
    expected_server_error = "Your current IP address (127.0.0.1) must be included in the IP allowlist to prevent account lockout."
    respx_mock.put(url, json=allowlist.model_dump(mode="json")).mock(
        return_value=httpx.Response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            json={"detail": expected_server_error},
        )
    )

    with use_profile(profile):
        invoke_and_assert(
            ["cloud", "ip-allowlist", "toggle", "127.0.0.1"],
            expected_code=1,
            expected_output_contains=expected_server_error,
            expected_line_count=1,
        )
