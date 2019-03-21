import pytest
from unittest.mock import MagicMock

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


class TestCreateNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = CreateNamespacedDeployment()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = CreateNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = CreateNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "test"})
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "b"})
        assert extensionsapi.create_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"a": "test"})

        assert extensionsapi.create_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = CreateNamespacedDeployment()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "a"})
        assert extensionsapi.create_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.create_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.create_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.create_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = CreateNamespacedDeployment(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.create_namespaced_deployment.call_args[1]["test"] == "a"


class TestDeleteNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = DeleteNamespacedDeployment()
        assert not task.deployment_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_name_raises_error(self):
        task = DeleteNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = DeleteNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(deployment_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = DeleteNamespacedDeployment(deployment_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = DeleteNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.delete_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = DeleteNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.delete_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.delete_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = DeleteNamespacedDeployment(deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.delete_namespaced_deployment.call_args[1]["test"] == "a"


class TestListNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = ListNamespacedDeployment()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ListNamespacedDeployment(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ListNamespacedDeployment()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ListNamespacedDeployment(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.list_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ListNamespacedDeployment(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.list_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.list_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ListNamespacedDeployment()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.list_namespaced_deployment.call_args[1]["test"] == "a"


class TestPatchNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = PatchNamespacedDeployment()
        assert not task.deployment_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_deployment_name_raises_error(self):
        task = PatchNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, deployment_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = PatchNamespacedDeployment(body={"test": "test"}, deployment_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "b"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, monkeypatch):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"a": "test"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = PatchNamespacedDeployment(deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "a"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = PatchNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = PatchNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.patch_namespaced_deployment.call_args[1]["test"] == "a"


class TestReadNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = ReadNamespacedDeployment()
        assert not task.deployment_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_name_raises_error(self):
        task = ReadNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReadNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(deployment_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReadNamespacedDeployment(deployment_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReadNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.read_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReadNamespacedDeployment(
            deployment_name="test", kube_kwargs={"test": "a"}
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.read_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.read_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReadNamespacedDeployment(deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.read_namespaced_deployment.call_args[1]["test"] == "a"


class TestReplaceNamespacedDeploymentTask:
    def test_empty_initialization(self):
        task = ReplaceNamespacedDeployment()
        assert not task.deployment_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_deployment_name_raises_error(self):
        task = ReplaceNamespacedDeployment()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, deployment_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReplaceNamespacedDeployment(
            body={"test": "test"}, deployment_name="test"
        )
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "b"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["body"] == {
            "test": "b"
        }

    def test_body_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"a": "test"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedDeployment(deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(body={"test": "a"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["body"] == {
            "test": "a"
        }

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedDeployment(
            body={"test": "a"}, kube_kwargs={"test": "a"}, deployment_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["a"] == "test"
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedDeployment(body={"test": "a"}, deployment_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.deployment.config", config)

        extensionsapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.deployment.client",
            MagicMock(ExtensionsV1beta1Api=MagicMock(return_value=extensionsapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert extensionsapi.replace_namespaced_deployment.call_args[1]["test"] == "a"
