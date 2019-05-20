from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.kubernetes import (
    CreateNamespacedPod,
    DeleteNamespacedPod,
    ListNamespacedPod,
    PatchNamespacedPod,
    ReadNamespacedPod,
    ReplaceNamespacedPod,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


class TestCreateNamespacedPodTask:
    def test_empty_initialization(self):
        task = CreateNamespacedPod()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = CreateNamespacedPod(
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
        task = CreateNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = CreateNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "test"})
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.create_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})

        assert coreapi.create_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = CreateNamespacedPod()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.create_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.create_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.create_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.create_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = CreateNamespacedPod(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.create_namespaced_pod.call_args[1]["test"] == "a"


class TestDeleteNamespacedPodTask:
    def test_empty_initialization(self):
        task = DeleteNamespacedPod()
        assert not task.pod_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = DeleteNamespacedPod(
            pod_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.pod_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self):
        task = DeleteNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = DeleteNamespacedPod()
        with pytest.raises(ValueError):
            task.run(pod_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = DeleteNamespacedPod(pod_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = DeleteNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.delete_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = DeleteNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.delete_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.delete_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = DeleteNamespacedPod(pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.delete_namespaced_pod.call_args[1]["test"] == "a"


class TestListNamespacedPodTask:
    def test_empty_initialization(self):
        task = ListNamespacedPod()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ListNamespacedPod(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ListNamespacedPod()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ListNamespacedPod(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.list_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ListNamespacedPod(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.list_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.list_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ListNamespacedPod()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.list_namespaced_pod.call_args[1]["test"] == "a"


class TestPatchNamespacedPodTask:
    def test_empty_initialization(self):
        task = PatchNamespacedPod()
        assert not task.pod_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = PatchNamespacedPod(
            pod_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.pod_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_pod_name_raises_error(self):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, pod_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = PatchNamespacedPod(body={"test": "test"}, pod_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.patch_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})
        assert coreapi.patch_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = PatchNamespacedPod(pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.patch_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.patch_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = PatchNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.patch_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.patch_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.patch_namespaced_pod.call_args[1]["test"] == "a"


class TestReadNamespacedPodTask:
    def test_empty_initialization(self):
        task = ReadNamespacedPod()
        assert not task.pod_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ReadNamespacedPod(
            pod_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.pod_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self):
        task = ReadNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReadNamespacedPod()
        with pytest.raises(ValueError):
            task.run(pod_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReadNamespacedPod(pod_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReadNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.read_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReadNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.read_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.read_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReadNamespacedPod(pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.read_namespaced_pod.call_args[1]["test"] == "a"


class TestReplaceNamespacedPodTask:
    def test_empty_initialization(self):
        task = ReplaceNamespacedPod()
        assert not task.pod_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ReplaceNamespacedPod(
            pod_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.pod_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_pod_name_raises_error(self):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, pod_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReplaceNamespacedPod(body={"test": "test"}, pod_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client.Configuration", conf_call
        )
        task.run()
        assert api_key == {"authorization": "test_key"}

    def test_body_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "b"})
        assert coreapi.replace_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"a": "test"})
        assert coreapi.replace_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedPod(pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(body={"test": "a"})
        assert coreapi.replace_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert coreapi.replace_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert coreapi.replace_namespaced_pod.call_args[1]["a"] == "test"
        assert coreapi.replace_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.pod.config", config)

        coreapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.pod.client",
            MagicMock(CoreV1Api=MagicMock(return_value=coreapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert coreapi.replace_namespaced_pod.call_args[1]["test"] == "a"
