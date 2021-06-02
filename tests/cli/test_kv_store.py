import uuid
from unittest.mock import MagicMock

from click.testing import CliRunner

from prefect.cli.kv_store import kv
from prefect.backend.kv_store import NON_CLOUD_BACKEND_ERROR_MESSAGE


def test_key_value_init():
    runner = CliRunner()
    result = runner.invoke(kv)
    assert result.exit_code == 0
    assert "Interact with Prefect Cloud KV Store" in result.output


def test_key_value_help():
    runner = CliRunner()
    result = runner.invoke(kv, ["--help"])
    assert result.exit_code == 0
    assert "Interact with Prefect Cloud KV Store" in result.output


def test_key_value_raises_on_server_backend(server_api):
    runner = CliRunner()
    result = runner.invoke(kv, ["set", "foo", "bar"])
    assert result.exit_code == 1
    assert NON_CLOUD_BACKEND_ERROR_MESSAGE in result.output


class TestSetKeyValue:
    def test_set_key_value(self, monkeypatch, cloud_api):
        set_kv = MagicMock(return_value=uuid.uuid4())
        monkeypatch.setattr("prefect.backend.kv_store.set_key_value", set_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["set", "foo", "bar"])
        assert result.exit_code == 0
        assert set_kv.called_with(key="foo", value="bar")
        assert "Key value pair set successfully" in result.stdout

    def test_set_key_value_logs_exception(self, monkeypatch, cloud_api):
        set_kv = MagicMock(side_effect=Exception())
        monkeypatch.setattr("prefect.backend.kv_store.set_key_value", set_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["set", "foo", "bar"])
        assert result.exit_code == 1
        assert set_kv.called_with(key="foo", value="bar")
        assert "An error occurred setting the key value pair" in result.stdout


class TestGetKeyValue:
    def test_get_key_value(self, monkeypatch, cloud_api):
        get_kv = MagicMock(return_value="bar")
        monkeypatch.setattr("prefect.backend.kv_store.get_key_value", get_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["get", "foo"])
        assert result.exit_code == 0
        assert get_kv.called_with(key="foo")
        assert "Key 'foo' has value 'bar'" in result.stdout

    def test_get_key_value_logs_exception(self, monkeypatch, cloud_api):
        get_kv = MagicMock(side_effect=Exception())
        monkeypatch.setattr("prefect.backend.kv_store.get_key_value", get_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["get", "foo"])
        assert result.exit_code == 1
        assert get_kv.called_with(key="foo")
        assert "Error retrieving value for key 'foo'" in result.stdout


class TestDeleteKeyValue:
    def test_delete_key_value(self, monkeypatch, cloud_api):
        delete_kv = MagicMock(return_value=True)
        monkeypatch.setattr("prefect.backend.kv_store.delete_key", delete_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["delete", "foo"])
        assert result.exit_code == 0
        assert delete_kv.called_with(key="foo")
        assert "Key 'foo' has been deleted" in result.stdout

    def test_delete_key_value_logs_exception(self, monkeypatch, cloud_api):
        delete_kv = MagicMock(side_effect=Exception())
        monkeypatch.setattr("prefect.backend.kv_store.delete_key", delete_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["delete", "foo"])
        assert result.exit_code == 1
        assert delete_kv.called_with(key="foo")
        assert "An error occurred deleting the key" in result.stdout


class TestListKeyValue:
    def test_list_key_value(self, monkeypatch, cloud_api):
        keys_list = ["key1", "key2", "key3"]
        list_kv = MagicMock(return_value=keys_list)
        monkeypatch.setattr("prefect.backend.kv_store.list_keys", list_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["list"])
        assert result.exit_code == 0
        assert list_kv.called
        for key in keys_list:
            assert key in result.stdout

    def test_list_key_value_warns_if_no_keys(self, monkeypatch, cloud_api):
        list_kv = MagicMock(return_value=[])
        monkeypatch.setattr("prefect.backend.kv_store.list_keys", list_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["list"])
        assert result.exit_code == 0
        assert list_kv.called
        assert "No keys found" in result.stdout

    def test_list_key_value_logs_exception(self, monkeypatch, cloud_api):
        list_kv = MagicMock(side_effect=Exception())
        monkeypatch.setattr("prefect.backend.kv_store.list_keys", list_kv)

        runner = CliRunner()
        result = runner.invoke(kv, ["list"])
        assert result.exit_code == 1
        assert list_kv.called
        assert "An error occurred when listing keys" in result.stdout
