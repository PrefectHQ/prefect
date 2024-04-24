from kubernetes.client.models import V1DeleteOptions, V1Service
from prefect_kubernetes.services import (
    create_namespaced_service,
    delete_namespaced_service,
    list_namespaced_service,
    patch_namespaced_service,
    read_namespaced_service,
    replace_namespaced_service,
)


async def test_create_namespaced_service(kubernetes_credentials, _mock_api_core_client):
    await create_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        new_service=V1Service(metadata={"name": "test-service"}),
        namespace="default",
    )

    assert _mock_api_core_client.create_namespaced_service.call_count == 1
    assert _mock_api_core_client.create_namespaced_service.call_args[1][
        "body"
    ].metadata == {"name": "test-service"}
    assert (
        _mock_api_core_client.create_namespaced_service.call_args[1]["namespace"]
        == "default"
    )


async def test_delete_namespaced_service(kubernetes_credentials, _mock_api_core_client):
    await delete_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        service_name="test-service",
        delete_options=V1DeleteOptions(grace_period_seconds=42),
        namespace="default",
    )

    assert _mock_api_core_client.delete_namespaced_service.call_count == 1
    assert (
        _mock_api_core_client.delete_namespaced_service.call_args[1]["name"]
        == "test-service"
    )
    assert (
        _mock_api_core_client.delete_namespaced_service.call_args[1][
            "body"
        ].grace_period_seconds
        == 42
    )
    assert (
        _mock_api_core_client.delete_namespaced_service.call_args[1]["namespace"]
        == "default"
    )


async def test_list_namespaced_service(kubernetes_credentials, _mock_api_core_client):
    await list_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        namespace="default",
    )

    assert _mock_api_core_client.list_namespaced_service.call_count == 1
    assert (
        _mock_api_core_client.list_namespaced_service.call_args[1]["namespace"]
        == "default"
    )


async def test_patch_namespaced_service(kubernetes_credentials, _mock_api_core_client):
    await patch_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        service_name="test-service-old",
        service_updates=V1Service(metadata={"name": "test-service"}),
        namespace="default",
    )

    assert _mock_api_core_client.patch_namespaced_service.call_count == 1
    assert (
        _mock_api_core_client.patch_namespaced_service.call_args[1]["name"]
        == "test-service-old"
    )
    assert _mock_api_core_client.patch_namespaced_service.call_args[1][
        "body"
    ].metadata == {"name": "test-service"}
    assert (
        _mock_api_core_client.patch_namespaced_service.call_args[1]["namespace"]
        == "default"
    )


async def test_read_namespaced_service(kubernetes_credentials, _mock_api_core_client):
    await read_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        service_name="test-service",
        namespace="default",
    )

    assert _mock_api_core_client.read_namespaced_service.call_count == 1
    assert (
        _mock_api_core_client.read_namespaced_service.call_args[1]["name"]
        == "test-service"
    )
    assert (
        _mock_api_core_client.read_namespaced_service.call_args[1]["namespace"]
        == "default"
    )


async def test_replace_namespaced_service(
    kubernetes_credentials, _mock_api_core_client
):
    await replace_namespaced_service.fn(
        kubernetes_credentials=kubernetes_credentials,
        service_name="test-service",
        new_service=V1Service(metadata={"labels": {"foo": "bar"}}),
        namespace="default",
    )

    assert _mock_api_core_client.replace_namespaced_service.call_count == 1
    assert (
        _mock_api_core_client.replace_namespaced_service.call_args[1]["name"]
        == "test-service"
    )
    assert _mock_api_core_client.replace_namespaced_service.call_args[1][
        "body"
    ].metadata == {"labels": {"foo": "bar"}}
    assert (
        _mock_api_core_client.replace_namespaced_service.call_args[1]["namespace"]
        == "default"
    )
