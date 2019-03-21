import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.kubernetes import CreateNamespacedJob
from prefect.utilities.configuration import set_temporary_config


class TestCreateNamespacedJobTask:
    def test_empty_initialization(self):
        task = CreateNamespacedJob()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = CreateNamespacedJob(
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
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "test"})
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(body={"test": "b"})
        assert task.body == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(body={"a": "test"})
        assert task.body == {"a": "test", "test": "a"}

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = CreateNamespacedJob()

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(body={"test": "a"})
        assert task.body == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(kube_kwargs={"test": "b"})
        assert task.kube_kwargs == {"test": "b"}

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(kube_kwargs={"a": "test"})
        assert task.kube_kwargs == {"a": "test", "test": "a"}

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        task.run(kube_kwargs={"test": "a"})
        assert task.kube_kwargs == {"test": "a"}
