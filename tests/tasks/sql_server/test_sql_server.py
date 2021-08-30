import pytest
from unittest.mock import MagicMock

import pyodbc

from prefect.tasks.sql_server import (
    SqlServerExecute,
    SqlServerExecuteMany,
    SqlServerFetch,
)


class TestSqlServerExecute:
    def test_construction(self):
        task = SqlServerExecute(db_name="test", user="test", host="test")
        assert task.commit is False

    def test_query_string_must_be_provided(self):
        task = SqlServerExecute(db_name="test", user="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_must_not_take_kwargs(self, monkeypatch):
        """
        pyodbc is written in c++ so it can't take kwargs for the
        execute commands otherwise it will throw an error.
        """
        cursor = MagicMock(spec=pyodbc.Cursor)
        connection = MagicMock(spec=pyodbc.Connection, cursor=cursor)
        sql_server_module_connect_method = MagicMock(return_value=connection)
        sql_server_connector_module = MagicMock(
            connect=sql_server_module_connect_method
        )

        monkeypatch.setattr(
            "prefect.tasks.sql_server.sql_server.pyodbc", sql_server_connector_module
        )

        task = SqlServerExecute(db_name="test", user="test", host="test")
        task.run(query="test_query", data=("test_data1", "test_data2"))

        for call in cursor.return_value.__enter__.return_value.execute.call_args_list:
            args, kwargs = call
            assert args == ("test_query", ("test_data1", "test_data2"))
            # kwargs must be an empty dict because .execute() can't take kwargs
            assert kwargs == dict()


class TestSqlServerExecuteMany:
    def test_construction(self):
        task = SqlServerExecuteMany(db_name="test", user="test", host="test")
        assert task.commit is False

    def test_query_string_must_be_provided(self):
        task = SqlServerExecuteMany(db_name="test", user="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_data_list_must_be_provided(self):
        task = SqlServerExecuteMany(
            db_name="test", user="test", host="test", query="test"
        )
        with pytest.raises(ValueError, match="A data list must be provided"):
            task.run()


class TestSqlServerFetch:
    def test_construction(self):
        task = SqlServerFetch(db_name="test", user="test", host="test")
        assert task.fetch == "one"

    def test_query_string_must_be_provided(self):
        task = SqlServerFetch(db_name="test", user="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_bad_fetch_param_raises(self):
        task = SqlServerFetch(db_name="test", user="test", host="test")
        with pytest.raises(
            ValueError,
            match=r"The 'fetch' parameter must be one of the following - \('one', 'many', 'all'\)",
        ):
            task.run(query="SELECT * FROM some_table", fetch="not a valid parameter")
