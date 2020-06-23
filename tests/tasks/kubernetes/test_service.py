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


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


class TestCreateNamespacedServiceTask:
    def test_empty_initialization(self, kube_secret):
        task = CreateNamespacedService()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = CreateNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = CreateNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_body_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_body_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_body_value_is_updated(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
    def test_empty_initialization(self, kube_secret):
        task = DeleteNamespacedService()
        assert not task.service_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_name_raises_error(self, kube_secret):
        task = DeleteNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = DeleteNamespacedService()
        with pytest.raises(ValueError):
            task.run(service_name=None)

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
    def test_empty_initialization(self, kube_secret):
        task = ListNamespacedService()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ListNamespacedService(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
    def test_empty_initialization(self, kube_secret):
        task = PatchNamespacedService()
        assert not task.service_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_service_name_raises_error(self, kube_secret):
        task = PatchNamespacedService()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, service_name=None)

    def test_body_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_body_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_body_value_is_updated(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
    def test_empty_initialization(self, kube_secret):
        task = ReadNamespacedService()
        assert not task.service_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_name_raises_error(self, kube_secret):
        task = ReadNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReadNamespacedService()
        with pytest.raises(ValueError):
            task.run(service_name=None)

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
    def test_empty_initialization(self, kube_secret):
        task = ReplaceNamespacedService()
        assert not task.service_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_service_name_raises_error(self, kube_secret):
        task = ReplaceNamespacedService()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, service_name=None)

    def test_body_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_body_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_body_value_is_updated(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_replaced(self, monkeypatch, kube_secret):
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

    def test_kube_kwargs_value_is_appended(self, monkeypatch, kube_secret):
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

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch, kube_secret):
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
