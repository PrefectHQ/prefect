import uuid

import httpx
import readchar
from starlette import status
from tests.cli.cloud.test_cloud import gen_test_workspace

from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    Profile,
    ProfilesCollection,
    save_profiles,
)
from prefect.testing.cli import invoke_and_assert


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
