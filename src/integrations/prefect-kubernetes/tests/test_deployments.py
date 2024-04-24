import pytest
from kubernetes.client.models import V1DeleteOptions, V1Deployment
from prefect_kubernetes.deployments import (
    create_namespaced_deployment,
    delete_namespaced_deployment,
    list_namespaced_deployment,
    patch_namespaced_deployment,
    read_namespaced_deployment,
    replace_namespaced_deployment,
)


async def test_create_namespaced_deployment(
    kubernetes_credentials, _mock_api_app_client
):
    await create_namespaced_deployment.fn(
        new_deployment=V1Deployment(metadata={"name": "test-deployment"}),
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert _mock_api_app_client.create_namespaced_deployment.call_args[1][
        "body"
    ].metadata == {"name": "test-deployment"}
    assert _mock_api_app_client.create_namespaced_deployment.call_args[1]["a"] == "test"


async def test_delete_namespaced_deployment(
    kubernetes_credentials, _mock_api_app_client
):
    await delete_namespaced_deployment.fn(
        kubernetes_credentials=kubernetes_credentials,
        deployment_name="test_deployment",
        delete_options=V1DeleteOptions(grace_period_seconds=42),
        a="test",
    )
    assert (
        _mock_api_app_client.delete_namespaced_deployment.call_args[1]["namespace"]
        == "default"
    )
    assert _mock_api_app_client.delete_namespaced_deployment.call_args[1]["a"] == "test"
    assert (
        _mock_api_app_client.delete_namespaced_deployment.call_args[1][
            "body"
        ].grace_period_seconds
        == 42
    )


async def test_bad_v1_delete_options(kubernetes_credentials, _mock_api_app_client):
    with pytest.raises(TypeError):
        await delete_namespaced_deployment.fn(
            kubernetes_credentials=kubernetes_credentials,
            deployment_name="test_deployment",
            delete_options=V1DeleteOptions(skrrrt_skrrrt="yeehaw"),
        )


async def test_list_namespaced_deployment(kubernetes_credentials, _mock_api_app_client):
    await list_namespaced_deployment.fn(
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_app_client.list_namespaced_deployment.call_args[1]["namespace"]
        == "ns"
    )
    assert _mock_api_app_client.list_namespaced_deployment.call_args[1]["a"] == "test"


async def test_patch_namespaced_deployment(
    kubernetes_credentials, _mock_api_app_client
):
    await patch_namespaced_deployment.fn(
        kubernetes_credentials=kubernetes_credentials,
        deployment_updates=V1Deployment(metadata={"name": "test-deployment"}),
        deployment_name="test_deployment",
        a="test",
    )
    assert _mock_api_app_client.patch_namespaced_deployment.call_args[1][
        "body"
    ].metadata == {"name": "test-deployment"}
    assert (
        _mock_api_app_client.patch_namespaced_deployment.call_args[1]["name"]
        == "test_deployment"
    )
    assert _mock_api_app_client.patch_namespaced_deployment.call_args[1]["a"] == "test"


async def test_read_namespaced_deployment(kubernetes_credentials, _mock_api_app_client):
    await read_namespaced_deployment.fn(
        deployment_name="test_deployment",
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_app_client.read_namespaced_deployment.call_args[1]["name"]
        == "test_deployment"
    )
    assert (
        _mock_api_app_client.read_namespaced_deployment.call_args[1]["namespace"]
        == "ns"
    )
    assert _mock_api_app_client.read_namespaced_deployment.call_args[1]["a"] == "test"


async def test_replace_namespaced_deployment(
    kubernetes_credentials, _mock_api_app_client
):
    await replace_namespaced_deployment.fn(
        deployment_name="test_deployment",
        new_deployment=V1Deployment(metadata={"name": "test-deployment"}),
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_app_client.replace_namespaced_deployment.call_args[1]["name"]
        == "test_deployment"
    )
    assert (
        _mock_api_app_client.replace_namespaced_deployment.call_args[1]["namespace"]
        == "ns"
    )
    assert _mock_api_app_client.replace_namespaced_deployment.call_args[1][
        "body"
    ].metadata == {"name": "test-deployment"}
    assert (
        _mock_api_app_client.replace_namespaced_deployment.call_args[1]["a"] == "test"
    )


@pytest.mark.parametrize(
    "task_accepting_deployment, deployment_kwarg",
    [
        (create_namespaced_deployment, "new_deployment"),
        (patch_namespaced_deployment, "deployment_updates"),
        (replace_namespaced_deployment, "new_deployment"),
    ],
)
async def test_bad_v1_deployment_kwargs(
    kubernetes_credentials, task_accepting_deployment, deployment_kwarg
):
    with pytest.raises(TypeError):
        await task_accepting_deployment.fn(
            **{deployment_kwarg: V1Deployment(skrrrt_skrrrt="yeehaw")},
            kubernetes_credentials=kubernetes_credentials,
        )
