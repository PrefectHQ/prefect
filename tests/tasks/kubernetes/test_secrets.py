from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.kubernetes import KubernetesSecret
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


@pytest.fixture
def client_read_namespaced_secret(monkeypatch):
    class SecretResult:
        def __init__(self):
            self.data = {"valide_secret": "cHJlZmVjdA==", "some_mumber": "MTIzNA=="}

    secret = MagicMock(return_value=SecretResult())
    # secret = MagicMock()
    monkeypatch.setattr("kubernetes.client.CoreV1Api.read_namespaced_secret", secret)
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.kubernetes.service.get_kubernetes_client",
        MagicMock(return_value=client),
    )
    return secret


class TestKubernetesSecretTask:
    def test_empty_initialization(self):
        task = KubernetesSecret()
        assert task.secret_name == None
        assert task.secret_key == None
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = KubernetesSecret(
            secret_name="test_secret",
            secret_key="mysecret",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.secret_name == "test_secret"
        assert task.secret_key == "mysecret"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_secret_name_raises_error(self):
        task = KubernetesSecret()
        with pytest.raises(ValueError):
            task.run()

    def test_empty_secret_key_raises_error(self):
        task = KubernetesSecret()
        with pytest.raises(ValueError):
            task.run()

    def test_params_are_passed_to_read_namespaced_secret(
        self, kube_secret, client_read_namespaced_secret
    ):
        task = KubernetesSecret(secret_name="secret-name", secret_key="valide_secret")

        task.run()
        assert client_read_namespaced_secret.call_args.kwargs["name"] == "secret-name"
        assert client_read_namespaced_secret.call_args.kwargs["namespace"] == "default"

    def test_secret_is_decoded_to_string(
        self, kube_secret, client_read_namespaced_secret
    ):
        task = KubernetesSecret(secret_name="secret-name", secret_key="valide_secret")

        secret_value = task.run()
        assert secret_value == "prefect"

    def test_secret_is_decoded_and_cast_to_int(
        self, kube_secret, client_read_namespaced_secret
    ):
        task = KubernetesSecret(
            secret_name="secret-name", secret_key="some_mumber", cast=int
        )

        secret_value = task.run()
        assert secret_value == 1234

    def test_secret_thow_value_error_if_secret_not_found_and_raise_flag_enabled(
        self, kube_secret, client_read_namespaced_secret
    ):
        task = KubernetesSecret(
            secret_name="secret-name",
            secret_key="key_that_doesnt_exist",
            raise_if_missing=True,
        )

        with pytest.raises(ValueError):
            task.run()

    def test_secret_return_None_if_secret_key_not_found(
        self, kube_secret, client_read_namespaced_secret
    ):
        task = KubernetesSecret(
            secret_name="secret-name",
            secret_key="key_that_doesnt_exist",
            raise_if_missing=False,
        )

        secret_value = task.run()
        assert secret_value == None
