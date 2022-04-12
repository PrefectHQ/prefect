import pytest
import pymysql
from unittest.mock import MagicMock

from prefect.tasks.mysql.mysql import MySQLExecute, MySQLFetch


class TestMySQLExecute:
    def test_construction(self):
        task = MySQLExecute(db_name="test", user="test", password="test", host="test")
        assert (task.commit is False) and (task.charset == "utf8mb4")

    def test_query_string_must_be_provided(self):
        task = MySQLExecute(db_name="test", user="test", password="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_run_args_used_over_init_args(self, monkeypatch):
        mock_connect = MagicMock()

        monkeypatch.setattr("pymysql.connect", mock_connect)
        task = MySQLExecute(
            db_name="test", user="test", password="initpassword", host="test"
        )
        task.run(query="select * from users", password="password_from_secret")

        assert mock_connect.call_args[1]["password"] == "password_from_secret"


class TestMySQLFetch:
    def test_construction(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        assert task.fetch == "one"

    def test_query_string_must_be_provided(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_bad_fetch_param_raises(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            ValueError,
            match=r"The 'fetch' parameter must be one of the following - \('one', 'many', 'all'\)",
        ):
            task.run(query="SELECT * FROM some_table", fetch="not a valid parameter")

    def test_construction_with_cursor_type_str(self):
        task = MySQLFetch(
            db_name="test",
            user="test",
            password="test",
            host="test",
            cursor_type="dictcursor",
        )
        assert task.cursor_type == "dictcursor"

    def test_construction_with_cursor_type_class(self):
        task = MySQLFetch(
            db_name="test",
            user="test",
            password="test",
            host="test",
            cursor_type=pymysql.cursors.DictCursor,
        )
        assert task.cursor_type == pymysql.cursors.DictCursor

    def test_unsupported_cursor_type_str_param_raises(self):
        cursor_type = "unsupportedcursor"

        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            TypeError,
            match=rf"'cursor_type' should be one of \['cursor', 'dictcursor', 'sscursor', 'ssdictcursor'\] or a full cursor class, got {cursor_type}",
        ):
            task.run(query="SELECT * FROM some_table", cursor_type=cursor_type)

    def test_bad_cursor_type_param_type_raises(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            TypeError,
            match=rf"'cursor_type' should be one of \['cursor', 'dictcursor', 'sscursor', 'ssdictcursor'\] or a full cursor class, got \['cursor'\]",
        ):
            task.run(query="SELECT * FROM some_table", cursor_type=["cursor"])

    def test_run_args_used_over_init_args(self, monkeypatch):
        mock_connect = MagicMock()

        monkeypatch.setattr("pymysql.connect", mock_connect)
        task = MySQLFetch(
            db_name="test", user="test", password="initpassword", host="test"
        )
        task.run(query="select * from users", password="password_from_secret")

        assert mock_connect.call_args[1]["password"] == "password_from_secret"
