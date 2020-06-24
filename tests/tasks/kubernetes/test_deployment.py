from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.kubernetes import (
    CreateNamespacedDeployment,
    DeleteNamespacedDeployment,
    ListNamespacedDeployment,
    PatchNamespacedDeployment,
    ReadNamespacedDeployment,
    ReplaceNamespacedDeployment,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


@pytest.fixture
def api_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.kubernetes.deployment.get_kubernetes_client",
        MagicMock(return_value=client),
    )
    return client


class TestCreateNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = CreateNamespacedDeployment()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = CreateNamespacedDeployment(
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = CreateNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = CreateNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedDeployment(body={"test": "a"})

        task.run(body={"test": "b"})
        assert api_client.create_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedDeployment(body={"test": "a"})

        task.run(body={"a": "test"})

        assert api_client.create_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedDeployment()

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run(body={"test": "a"})
        assert api_client.create_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedDeployment(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.create_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedDeployment(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.create_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.create_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedDeployment(body={"test": "a"})

        task.run(kube_kwargs={"test": "a"})
        assert api_client.create_namespaced_deployment.call_args[1]["test"] == "a"


class TestDeleteNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = DeleteNamespacedDeployment()
        assert not task.deployment_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = DeleteNamespacedDeployment(
            deployment_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.deployment_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self, kube_secret):
        task = DeleteNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = DeleteNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(deployment_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = DeleteNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.delete_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = DeleteNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.delete_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.delete_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = DeleteNamespacedDeployment(deployment_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.delete_namespaced_deployment.call_args[1]["test"] == "a"


class TestListNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = ListNamespacedDeployment()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ListNamespacedDeployment(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ListNamespacedDeployment(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.list_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ListNamespacedDeployment(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.list_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.list_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ListNamespacedDeployment()

        task.run(kube_kwargs={"test": "a"})
        assert api_client.list_namespaced_deployment.call_args[1]["test"] == "a"


class TestPatchNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = PatchNamespacedDeployment()
        assert not task.deployment_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = PatchNamespacedDeployment(
            deployment_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.deployment_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_deployment_name_raises_error(self, kube_secret):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, deployment_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(body={"test": "b"})
        assert api_client.patch_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(body={"a": "test"})
        assert api_client.patch_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(deployment_name="test")

        task.run(body={"test": "a"})
        assert api_client.patch_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.patch_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.patch_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.patch_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.patch_namespaced_deployment.call_args[1]["test"] == "a"


class TestReadNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = ReadNamespacedDeployment()
        assert not task.deployment_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ReadNamespacedDeployment(
            deployment_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.deployment_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self, kube_secret):
        task = ReadNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReadNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(deployment_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReadNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.read_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReadNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.read_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.read_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReadNamespacedDeployment(deployment_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.read_namespaced_deployment.call_args[1]["test"] == "a"


class TestReplaceNamespacedDeploymentTask:
    def test_empty_initialization(self, kube_secret):
        task = ReplaceNamespacedDeployment()
        assert not task.deployment_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ReplaceNamespacedDeployment(
            deployment_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.deployment_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_deployment_name_raises_error(self, kube_secret):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, deployment_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(body={"test": "b"})
        assert api_client.replace_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(body={"a": "test"})
        assert api_client.replace_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(deployment_name="test")

        task.run(body={"test": "a"})
        assert api_client.replace_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.replace_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.replace_namespaced_deployment.call_args[1]["a"] == "test"
        assert api_client.replace_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.replace_namespaced_deployment.call_args[1]["test"] == "a"
