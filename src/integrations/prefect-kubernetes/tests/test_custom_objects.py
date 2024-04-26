import pytest
from kubernetes.client.exceptions import ApiValueError
from prefect_kubernetes.custom_objects import (
    create_namespaced_custom_object,
    delete_namespaced_custom_object,
    get_namespaced_custom_object,
    get_namespaced_custom_object_status,
    list_namespaced_custom_object,
    patch_namespaced_custom_object,
    replace_namespaced_custom_object,
)


async def test_null_body_raises_error(kubernetes_credentials):
    with pytest.raises(ApiValueError):
        await create_namespaced_custom_object.fn(
            group="my-group",
            version="v1",
            plural="ops",
            body=None,
            kubernetes_credentials=kubernetes_credentials,
        )
    with pytest.raises(ApiValueError):
        await patch_namespaced_custom_object.fn(
            group="my-group",
            version="v1",
            plural="ops",
            name="test-name",
            body=None,
            kubernetes_credentials=kubernetes_credentials,
        )
    with pytest.raises(ApiValueError):
        await replace_namespaced_custom_object.fn(
            group="my-group",
            version="v1",
            plural="ops",
            name="test-name",
            body=None,
            kubernetes_credentials=kubernetes_credentials,
        )


async def test_create_namespaced_crd(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await create_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        body={
            "api": "v1",
            "kind": "op",
            "metadata": {
                "name": "test",
            },
        },
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.create_namespaced_custom_object.call_args[1][
            "a"
        ]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.create_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.create_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.create_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )
    # We can't have models for Custom Resources.
    assert _mock_api_custom_objects_client.create_namespaced_custom_object.call_args[1][
        "body"
    ]["metadata"] == {"name": "test"}


async def test_get_namespaced_custom_object(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await get_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        name="test-name",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object.call_args[1]["a"]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )
    # We can't have models for Custom Resources.
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object.call_args[1][
            "name"
        ]
        == "test-name"
    )


async def test_get_namespaced_custom_object_status(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await get_namespaced_custom_object_status.fn(
        group="my-group",
        version="v1",
        plural="ops",
        name="test-name",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object_status.call_args[
            1
        ]["a"]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object_status.call_args[
            1
        ]["group"]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object_status.call_args[
            1
        ]["version"]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object_status.call_args[
            1
        ]["plural"]
        == "ops"
    )
    # We can't have models for Custom Resources.
    assert (
        _mock_api_custom_objects_client.get_namespaced_custom_object_status.call_args[
            1
        ]["name"]
        == "test-name"
    )


async def test_delete_namespaced_custom_object(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await delete_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        name="test-name",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.delete_namespaced_custom_object.call_args[1][
            "a"
        ]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.delete_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.delete_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.delete_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )
    # We can't have models for Custom Resources.
    assert (
        _mock_api_custom_objects_client.delete_namespaced_custom_object.call_args[1][
            "name"
        ]
        == "test-name"
    )


async def test_list_namespaced_custom_object(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await list_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.list_namespaced_custom_object.call_args[1]["a"]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.list_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.list_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.list_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )


async def test_patch_namespaced_custom_object(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await patch_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        name="test-name",
        body={
            "api": "v1",
            "kind": "op",
            "metadata": {
                "name": "test",
            },
        },
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1]["a"]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )
    assert (
        _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1][
            "name"
        ]
        == "test-name"
    )
    assert _mock_api_custom_objects_client.patch_namespaced_custom_object.call_args[1][
        "body"
    ]["metadata"] == {"name": "test"}


async def test_replace_namespaced_custom_object(
    kubernetes_credentials, _mock_api_custom_objects_client
):
    await replace_namespaced_custom_object.fn(
        group="my-group",
        version="v1",
        plural="ops",
        name="test-name",
        body={
            "api": "v1",
            "kind": "op",
            "metadata": {
                "name": "test",
            },
        },
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert (
        _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[1][
            "a"
        ]
        == "test"
    )

    assert (
        _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[1][
            "group"
        ]
        == "my-group"
    )
    assert (
        _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[1][
            "version"
        ]
        == "v1"
    )
    assert (
        _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[1][
            "plural"
        ]
        == "ops"
    )
    assert (
        _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[1][
            "name"
        ]
        == "test-name"
    )
    assert _mock_api_custom_objects_client.replace_namespaced_custom_object.call_args[
        1
    ]["body"]["metadata"] == {"name": "test"}
