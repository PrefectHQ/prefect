import hvac
import pytest
import cloudpickle
from unittest.mock import MagicMock

# prefect imports
from prefect import prefect, Flow, task
from prefect.engine.results import SecretResult

# local imports
from prefect.tasks.secrets.vault_secret import VaultSecret


@task
def vault_secret_test_task(secret: str):
    """
    helper task for testing use of VaultSecret within a flow
    """
    return secret


def test_vault_secret_use_in_flow(monkeypatch, server_api):
    """
    Verify use of VaultSecret in a flow defintion
    """
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    hvac.Client.is_authenticated = MagicMock(return_value=True)
    hvac.Client.auth_approle = MagicMock(return_value=None)
    mock_vault_response = {"data": {"data": {"fake-key": "fake-value"}}}
    hvac.api.secrets_engines.KvV2.read_secret_version = MagicMock(
        return_value=mock_vault_response
    )
    vault_creds = {"VAULT_TOKEN": "fake-token"}
    with prefect.context(secrets={"VAULT_CREDENTIALS": vault_creds}):
        with Flow("vault-secret-test-flow") as flow:
            secret = VaultSecret("secret/fake-path")
            ret = vault_secret_test_task(secret)

        state = flow.run()
        assert state.result[ret].result == {"fake-key": "fake-value"}


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


def test_vault_addr_env_var_missing(monkeypatch, server_api):
    monkeypatch.delenv("vault_addr", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    with pytest.raises(ValueError, match=r"var not found"):
        task = VaultSecret("fake-no-vault-addr-secret")
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
        task = VaultSecret("fake-no-vault-addr-secret")
        task.run()


def test_vault_auth_missing(monkeypatch, server_api):
    """
    Verify that either VAULT_TOKEN or VAULT_ROLE_ID/VAULT_SECRET_ID are required.
    """
    monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
    with pytest.raises(ValueError, match=r"Supported methods"), prefect.context(
        secrets={"VAULT_CREDENTIALS": {"WRONG_TOKEN": "wrong-token-value"}}
    ):
        task = VaultSecret("fake-remote-secret")
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
        task = VaultSecret("secret/fake-path")
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
        task = VaultSecret(
            "secret/fake-path", vault_credentials_secret="MY_VAULT_CREDS"
        )
        out = task.run()
        assert out == {"fake-key": "fake-value"}
