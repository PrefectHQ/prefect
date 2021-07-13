import hvac
import pytest
import cloudpickle
from typing import Any
from unittest.mock import MagicMock

# prefect imports
from prefect import prefect, Task
from prefect.engine.results import SecretResult
from prefect.utilities.tasks import defaults_from_attrs

# local imports
from prefect.tasks.secrets.vault_secret import VaultSecret


def test_create_vault_var():
    """
    Verify class instance creation
    """
    vs = VaultSecret("fake-secret")
    assert vs.name == "fake-secret"
    assert isinstance(vs, VaultSecret)
    assert isinstance(vs.result, SecretResult)


def test_secret_is_pickleable():
    """
    Verify secret class instance can be pickeled
    """
    vs = VaultSecret("fake-pickeled-vault-secret")
    new = cloudpickle.loads(cloudpickle.dumps(vs))
    assert new.name == "fake-pickeled-vault-secret"
    assert isinstance(new.result, SecretResult)


# --- Test Harness Task ---
class VaultSecretTestTask(Task):
    """
    Test harness task for testing VaultSecrets
    Provides example of using VaultSecrets from a task

    Returns a vault secret value from a vault secret key
    """

    def __init__(self, secret_key: str = None, **kwargs: Any):
        self.secret_key = secret_key
        kwargs.setdefault("name", secret_key)
        super().__init__(**kwargs)

    @defaults_from_attrs("secret_key")
    def run(self, secret_key: str = None, vault_credentials_secret: str = None):
        # self.logger.info("--- starting test task ---")
        if vault_credentials_secret is None:
            fake_secret = VaultSecret(self.secret_key)
        else:
            fake_secret = VaultSecret(
                self.secret_key, vault_credentials_secret=vault_credentials_secret
            )
        fake_secret_val = fake_secret.run()
        # self.logger.info("--- leaving test task ---")
        return fake_secret_val


# --- end VaultSecretTestTask ---


def test_vault_addr_env_var_missing(monkeypatch, server_api):
    monkeypatch.delenv("vault_addr", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    with pytest.raises(ValueError, match=r"var not found"):
        task = VaultSecretTestTask("fake-no-vault-addr-secret")
        task.run()


@pytest.mark.parametrize("vault_var", ["vault_addr", "VAULT_ADDR"])
def test_vault_addr_from_env_var(monkeypatch, vault_var, server_api):
    """
    Verify accepting either upper case or lower case vault addr env vars
    """
    monkeypatch.setenv(vault_var, "http://localhost:8200")
    with pytest.raises(
        ValueError, match=r"Local Secret \"VAULT_CREDENTIALS\" was not found."
    ):
        task = VaultSecretTestTask("fake-no-vault-addr-secret")
        task.run()


def test_vault_auth_missing(monkeypatch, server_api):
    """
    Verify that either VAULT_TOKEN or VAULT_ROLE_ID/VAULT_SECRET_ID are required.
    """
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    with pytest.raises(ValueError, match=r"Supported methods"), prefect.context(
        secrets={"VAULT_CREDENTIALS": {"WRONG_TOKEN": "wrong-token-value"}}
    ):
        task = VaultSecretTestTask("fake-remote-secret")
        out = task.run()
        assert out == "assert-wont-be-reached"


@pytest.mark.parametrize(
    "vault_creds",
    [
        {"VAULT_TOKEN": "fake-vault-token"},
        {
            "VAULT_ROLE_ID": "fake-vault-role-id",
            "VAULT_SECRET_ID": "fake-vault-secret-id",
        },
    ],
)
def test_vault_secret_lookup(monkeypatch, vault_creds, server_api):
    """
    Mocked lookup of a secret from vault
    The prefect server/cloud secret also mocked
    """
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    hvac.Client.is_authenticated = MagicMock(return_value=True)
    hvac.Client.auth_approle = MagicMock(return_value=None)
    mock_vault_response = {"data": {"data": {"fake-key": "fake-value"}}}
    hvac.api.secrets_engines.KvV2.read_secret_version = MagicMock(
        return_value=mock_vault_response
    )
    with prefect.context(secrets={"VAULT_CREDENTIALS": vault_creds}):
        task = VaultSecretTestTask("secret/fake-path")
        out = task.run()
        assert out == {"fake-key": "fake-value"}


@pytest.mark.parametrize(
    "vault_creds",
    [
        {"VAULT_TOKEN": "fake-vault-token"},
        {
            "VAULT_ROLE_ID": "fake-vault-role-id",
            "VAULT_SECRET_ID": "fake-vault-secret-id",
        },
    ],
)
def test_vault_secret_lookup_using_alt_creds(monkeypatch, vault_creds, server_api):
    """
    Mocked lookup of a secret from vault
    The prefect server/cloud secret also mocked
    """
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    hvac.Client.is_authenticated = MagicMock(return_value=True)
    hvac.Client.auth_approle = MagicMock(return_value=None)
    mock_vault_response = {"data": {"data": {"fake-key": "fake-value"}}}
    hvac.api.secrets_engines.KvV2.read_secret_version = MagicMock(
        return_value=mock_vault_response
    )
    with prefect.context(secrets={"MY_VAULT_CREDS": vault_creds}):
        task = VaultSecretTestTask("secret/fake-path")
        out = task.run(vault_credentials_secret="MY_VAULT_CREDS")
        assert out == {"fake-key": "fake-value"}
