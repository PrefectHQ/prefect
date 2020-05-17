import pendulum
import pytest
import prefect
from prefect.tasks.secrets import EnvVarSecret


def test_create_envvarsecret_requires_name():
    with pytest.raises(TypeError, match="required positional argument: 'name'"):
        EnvVarSecret()


def test_init_with_name():
    e = EnvVarSecret(name="FOO")
    assert e.name == "FOO"


def test_default_cast_is_none():
    e = EnvVarSecret(name="FOO")
    assert e.cast is None


def test_run_secret(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(name="FOO")
    assert e.run() == "1"


def test_run_secret_without_name_set_returns_none(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(name="FOO")
    assert e.run() is None


def test_run_secret_with_new_name_at_runtime(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(name="FOO")
    assert e.run(name="BAR") is None


def test_run_secret_with_new_name_at_runtime_and_raise_missing(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(name="FOO", raise_if_missing=True)
    with pytest.raises(ValueError, match="variable not set"):
        e.run(name="BAR")


def test_run_secret_without_name_set_raises(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(name="FOO", raise_if_missing=True)
    with pytest.raises(ValueError, match="variable not set"):
        e.run()


def test_run_secret_with_cast(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    e = EnvVarSecret(name="FOO", cast=int)
    assert e.run() == 1


def test_run_secret_without_name_set_returns_none_even_if_cast_set(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(name="FOO", cast=int)
    assert e.run() is None


def test_run_secret_without_name_set_raises_with_cast(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    e = EnvVarSecret(name="FOO", raise_if_missing=True, cast=int)
    with pytest.raises(ValueError, match="variable not set"):
        e.run()


def test_run_secret_with_cast_datetime(monkeypatch):
    monkeypatch.setenv("FOO", "2019-01-02 03:04:05")
    e = EnvVarSecret(name="FOO", cast=pendulum.parse)
    assert e.run() == pendulum.datetime(2019, 1, 2, 3, 4, 5)
