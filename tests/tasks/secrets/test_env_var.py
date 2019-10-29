import pendulum
import pytest
import prefect
from prefect.tasks.secrets import EnvVarSecret


def test_create_envvarsecret_requires_env_var():
    with pytest.raises(TypeError, match="required positional argument: 'env_var'"):
        EnvVarSecret()


def test_name_defaults_to_env_var():
    e = EnvVarSecret(env_var="FOO")
    assert e.env_var == "FOO"
    assert e.name == "FOO"


def test_name_can_be_customized():
    e = EnvVarSecret(env_var="FOO", name="BAR")
    assert e.env_var == "FOO"
    assert e.name == "BAR"


def test_default_cast_is_none():
    e = EnvVarSecret(env_var="FOO")
    assert e.cast is None


def test_run_secret(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(env_var="FOO")
    assert e.run() == "1"


def test_run_secret_without_env_var_set_returns_none(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(env_var="FOO")
    assert e.run() is None


def test_run_secret_with_cast(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(env_var="FOO", cast=int)
    assert e.run() == 1


def test_run_secret_without_env_var_set_returns_none_even_if_cast_set(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(env_var="FOO", cast=int)
    assert e.run() is None


def test_run_secret_with_cast_datetime(monkeypatch):
    monkeypatch.setenv("FOO", "2019-01-02 03:04:05")
    e = EnvVarSecret(env_var="FOO", cast=pendulum.parse)
    assert e.run() == pendulum.datetime(2019, 1, 2, 3, 4, 5)
