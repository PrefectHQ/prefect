from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.kubernetes import (
    CreateNamespacedService,
    DeleteNamespacedService,
    ListNamespacedService,
    PatchNamespacedService,
    ReadNamespacedService,
    ReplaceNamespacedService,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


class TestCreateNamespacedServiceTask:
    def test_empty_initialization(self):
        task = CreateNamespacedService()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = CreateNamespacedService(
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
        task = CreateNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = CreateNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "test"})
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.create_namespaced_service.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})

        assert coreapi.create_namespaced_service.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = CreateNamespacedService()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.create_namespaced_service.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.create_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.create_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.create_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = CreateNamespacedService(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.create_namespaced_service.call_args[1]["test"] == "a"


class TestDeleteNamespacedServiceTask:
    def test_empty_initialization(self):
        task = DeleteNamespacedService()
        assert not task.service_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = DeleteNamespacedService(
            service_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.service_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self):
        task = DeleteNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = DeleteNamespacedService()
        with pytest.raises(ValueError):
            task.run(service_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = DeleteNamespacedService(service_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = DeleteNamespacedService(service_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.delete_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = DeleteNamespacedService(service_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.delete_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.delete_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = DeleteNamespacedService(service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.delete_namespaced_service.call_args[1]["test"] == "a"


class TestListNamespacedServiceTask:
    def test_empty_initialization(self):
        task = ListNamespacedService()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ListNamespacedService(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ListNamespacedService()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ListNamespacedService(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.list_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ListNamespacedService(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.list_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.list_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ListNamespacedService()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.list_namespaced_service.call_args[1]["test"] == "a"


class TestPatchNamespacedServiceTask:
    def test_empty_initialization(self):
        task = PatchNamespacedService()
        assert not task.service_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = PatchNamespacedService(
            service_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.service_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_service_name_raises_error(self):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, service_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = PatchNamespacedService(body={"test": "test"}, service_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.patch_namespaced_service.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = PatchNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})
        assert coreapi.patch_namespaced_service.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = PatchNamespacedService(service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.patch_namespaced_service.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedService(
            body={"test": "a"}, kube_kwargs={"test": "a"}, service_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.patch_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = PatchNamespacedService(
            body={"test": "a"}, kube_kwargs={"test": "a"}, service_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.patch_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.patch_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = PatchNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.patch_namespaced_service.call_args[1]["test"] == "a"


class TestReadNamespacedServiceTask:
    def test_empty_initialization(self):
        task = ReadNamespacedService()
        assert not task.service_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ReadNamespacedService(
            service_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.service_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self):
        task = ReadNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReadNamespacedService()
        with pytest.raises(ValueError):
            task.run(service_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReadNamespacedService(service_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReadNamespacedService(service_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.read_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReadNamespacedService(service_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.read_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.read_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReadNamespacedService(service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.read_namespaced_service.call_args[1]["test"] == "a"


class TestReplaceNamespacedServiceTask:
    def test_empty_initialization(self):
        task = ReplaceNamespacedService()
        assert not task.service_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ReplaceNamespacedService(
            service_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.service_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_service_name_raises_error(self):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, service_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReplaceNamespacedService(body={"test": "test"}, service_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.replace_namespaced_service.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})
        assert coreapi.replace_namespaced_service.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedService(service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.replace_namespaced_service.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedService(
            body={"test": "a"}, kube_kwargs={"test": "a"}, service_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.replace_namespaced_service.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedService(
            body={"test": "a"}, kube_kwargs={"test": "a"}, service_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.replace_namespaced_service.call_args[1]["a"] == "test"
        assert coreapi.replace_namespaced_service.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedService(body={"test": "a"}, service_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.service.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.service.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.replace_namespaced_service.call_args[1]["test"] == "a"
