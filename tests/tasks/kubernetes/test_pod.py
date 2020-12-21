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
    ReadNamespacedPodLogs,
)
from prefect.utilities.configuration import set_temporary_config

from kubernetes.client.rest import ApiException


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


@pytest.fixture
def api_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.kubernetes.pod.get_kubernetes_client",
        MagicMock(return_value=client),
    )
    return client


@pytest.fixture
def stream(monkeypatch):
    stream = MagicMock(return_value=["msg"])
    monkeypatch.setattr(
        "kubernetes.watch.watch.Watch.stream",
        stream,
    )

    return stream


class TestCreateNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = CreateNamespacedPod()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = CreateNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = CreateNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedPod(body={"test": "a"})

        task.run(body={"test": "b"})
        assert api_client.create_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedPod(body={"test": "a"})

        task.run(body={"a": "test"})

        assert api_client.create_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedPod()

        task.run(body={"test": "a"})
        assert api_client.create_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedPod(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.create_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedPod(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.create_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.create_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedPod(body={"test": "a"})

        task.run(kube_kwargs={"test": "a"})
        assert api_client.create_namespaced_pod.call_args[1]["test"] == "a"


class TestDeleteNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = DeleteNamespacedPod()
        assert not task.pod_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_name_raises_error(self, kube_secret):
        task = DeleteNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = DeleteNamespacedPod()
        with pytest.raises(ValueError):
            task.run(pod_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = DeleteNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.delete_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = DeleteNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.delete_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.delete_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = DeleteNamespacedPod(pod_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.delete_namespaced_pod.call_args[1]["test"] == "a"


class TestListNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = ListNamespacedPod()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ListNamespacedPod(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ListNamespacedPod(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.list_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ListNamespacedPod(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.list_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.list_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ListNamespacedPod()

        task.run(kube_kwargs={"test": "a"})
        assert api_client.list_namespaced_pod.call_args[1]["test"] == "a"


class TestPatchNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = PatchNamespacedPod()
        assert not task.pod_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_pod_name_raises_error(self, kube_secret):
        task = PatchNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, pod_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(body={"test": "b"})
        assert api_client.patch_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(body={"a": "test"})
        assert api_client.patch_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedPod(pod_name="test")

        task.run(body={"test": "a"})
        assert api_client.patch_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.patch_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.patch_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.patch_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.patch_namespaced_pod.call_args[1]["test"] == "a"


class TestReadNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = ReadNamespacedPod()
        assert not task.pod_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_name_raises_error(self, kube_secret):
        task = ReadNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReadNamespacedPod()
        with pytest.raises(ValueError):
            task.run(pod_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReadNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.read_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReadNamespacedPod(pod_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.read_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.read_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReadNamespacedPod(pod_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.read_namespaced_pod.call_args[1]["test"] == "a"


class TestReplaceNamespacedPodTask:
    def test_empty_initialization(self, kube_secret):
        task = ReplaceNamespacedPod()
        assert not task.pod_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
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

    def test_empty_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_pod_name_raises_error(self, kube_secret):
        task = ReplaceNamespacedPod()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, pod_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(body={"test": "b"})
        assert api_client.replace_namespaced_pod.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(body={"a": "test"})
        assert api_client.replace_namespaced_pod.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(pod_name="test")

        task.run(body={"test": "a"})
        assert api_client.replace_namespaced_pod.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.replace_namespaced_pod.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(
            body={"test": "a"}, kube_kwargs={"test": "a"}, pod_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.replace_namespaced_pod.call_args[1]["a"] == "test"
        assert api_client.replace_namespaced_pod.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedPod(body={"test": "a"}, pod_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.replace_namespaced_pod.call_args[1]["test"] == "a"


class TestReadNamespacedPodLogs:
    def _on_log_entry(message):
        pass

    def test_empty_initialization(self, kube_secret):
        task = ReadNamespacedPodLogs()
        assert not task.pod_name
        assert task.namespace == "default"
        assert task.on_log_entry == None
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ReadNamespacedPodLogs(
            pod_name="test",
            namespace="test",
            on_log_entry=self._on_log_entry,
            kubernetes_api_key_secret="test",
        )
        assert task.pod_name == "test"
        assert task.namespace == "test"
        assert task.on_log_entry == self._on_log_entry
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self, kube_secret):
        task = ReadNamespacedPodLogs()
        with pytest.raises(ValueError):
            task.run()

    def test_log_is_read_once(self, kube_secret, api_client):
        task = ReadNamespacedPodLogs(pod_name="test")

        task.run()
        assert api_client.read_namespaced_pod_log.call_count == 1
        assert api_client.read_namespaced_pod_log.call_args[1]["name"] == "test"

    def test_log_is_streamed(self, kube_secret, api_client, stream):
        on_log_entry = MagicMock()
        task = ReadNamespacedPodLogs(pod_name="test", on_log_entry=on_log_entry)

        task.run()
        assert stream.call_count == 1
        assert stream.call_args[0][0] == api_client.read_namespaced_pod_log
        assert stream.call_args[1]["name"] == "test"

        assert on_log_entry.call_count == 1
        assert on_log_entry.call_args[0][0] == "msg"

    def test_log_stream_retry_on_410(self, kube_secret, api_client, stream):
        stream.side_effect = [ApiException(status=410), ["msg 2"]]

        on_log_entry = MagicMock()
        task = ReadNamespacedPodLogs(pod_name="test", on_log_entry=on_log_entry)

        task.run()
        assert stream.call_count == 2
        assert stream.call_args[0][0] == api_client.read_namespaced_pod_log
        assert stream.call_args[1]["name"] == "test"

        assert on_log_entry.call_count == 1
        assert on_log_entry.call_args[0][0] == "msg 2"

    def test_log_stream_raise_on_non_410(self, kube_secret, api_client, stream):
        stream.side_effect = [ValueError, ["msg 2"]]

        on_log_entry = MagicMock()
        task = ReadNamespacedPodLogs(pod_name="test", on_log_entry=on_log_entry)

        with pytest.raises(ValueError):
            task.run()

        assert stream.call_count == 1
        assert stream.call_args[0][0] == api_client.read_namespaced_pod_log
        assert stream.call_args[1]["name"] == "test"
