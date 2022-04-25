from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest
import snowflake.connector as sf
from snowflake.connector.cursor import DictCursor, SnowflakeCursor

from prefect.tasks.snowflake import SnowflakeQueriesFromFile, SnowflakeQuery


@pytest.fixture
def sql_file(tmpdir):
    # write a temporary file that holds a query for testing
    query = """
        SHOW DATABASES;
        USE DEMO_DB;
    """
    p = Path(tmpdir / "test_sql.sql")
    p.write_text(query)
    return tmpdir / "test_sql.sql"


class TestSnowflakeQuery:
    def test_construction(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None
        assert task.authenticator is None

    def test_runtime(self, monkeypatch):
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection, cursor=cursor)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "TESTDB"
        ]

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        # task needs to allow for purely runtime arguments
        output = SnowflakeQuery().run(
            account="test", user="test", password="test", query="SHOW DATABASES"
        )

        assert output == ["TESTDB"]
        for call in snowflake_module_connect_method.call_args_list:
            args, kwargs = call
            assert kwargs == dict(
                account="test",
                user="test",
                password="test",
                application="Prefect_SnowflakeQuery",
            )

    def test_required_parameters(self):
        # missing account
        with pytest.raises(ValueError):
            SnowflakeQuery().run(user="test", password="test")
        # missing user
        with pytest.raises(ValueError):
            SnowflakeQuery().run(account="test", password="test")
        # missing password
        with pytest.raises(ValueError):
            SnowflakeQuery().run(account="test", user="test")
        # missing query
        with pytest.raises(ValueError):
            SnowflakeQuery().run(account="test", user="test", password="test")

    def test_query_string_must_be_provided(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_error_must_pass_through(self, monkeypatch):
        snowflake_module_connect_method = MagicMock()
        connection = MagicMock(spec=sf.SnowflakeConnection)
        cursor = MagicMock(spec=sf.DictCursor)

        # link all the mocks together appropriately
        snowflake_module_connect_method.return_value = connection
        connection.cursor = cursor

        # database cursors can be ugly to mock given  the use of __enter__
        cursor.return_value.__enter__.return_value.execute.side_effect = (
            sf.DatabaseError("Invalid query")
        )
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )

        with pytest.raises(sf.errors.DatabaseError, match="Invalid query"):
            task.run(query="SELECT * FROM foo")

    def test_execute_fetchall(self, monkeypatch):
        """
        Tests that the SnowflakeQuery Task calls the fetchall method on the
        cursor. This is to prevent future code edits from returning the cursor
        object because that cursors are not pickleable.
        """
        snowflake_module_connect_method = MagicMock()
        connection = MagicMock(spec=sf.SnowflakeConnection)
        cursor = MagicMock(spec=sf.DictCursor)

        # link all the mocks together appropriately
        snowflake_module_connect_method.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "TESTDB"
        ]
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        query = "SHOW DATABASES"
        output = SnowflakeQuery(
            account="test", user="test", password="test", query=query
        ).run()

        assert output == ["TESTDB"]

    def test_run_method_accepts_alternate_cursor(self, monkeypatch):
        """
        Tests that the default cursor used by the Snowflake connection
        is of the type `SnowflakeCursor`, and that the cursor type can
        be overriden by providing a different cursor type to the
        `cursor_type` keyword argument.
        """
        snowflake_module_connect_method = MagicMock()
        connection = MagicMock(spec=sf.SnowflakeConnection)
        default_cursor = MagicMock(spec=sf.cursor.SnowflakeCursor)
        dict_cursor = MagicMock(spec=sf.cursor.DictCursor)

        # link all the mocks together appropriately
        snowflake_module_connect_method.return_value = connection

        # setting fetchall return
        default_cursor.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "1",
            "2",
            "3",
        ]
        dict_cursor.__enter__.return_value.execute.return_value.fetchall.return_value = {
            "one": "1",
            "two": "2",
            "three": "3",
        }
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        def mock_cursor(cursor_class: SnowflakeCursor) -> SnowflakeCursor:
            if cursor_class == DictCursor:
                return dict_cursor
            else:
                return default_cursor

        connection.cursor = mock_cursor

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        query = "select * from numbers"
        task = SnowflakeQuery(account="test", user="test", password="test", query=query)

        default_cursor_output = task.run(cursor_type=SnowflakeCursor)
        dict_cursor_output = task.run(cursor_type=DictCursor)

        assert default_cursor_output == ["1", "2", "3"]
        assert dict_cursor_output == {"one": "1", "two": "2", "three": "3"}


class TestSnowflakeQueriesFromFile:
    def test_construction(self):
        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None

    def test_runtime_arguments(self, monkeypatch, sql_file):
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # link all the mocks together appropriately
        connection.execute_string.return_value = [cursor]

        # setting fetchall return
        cursor.fetchall.return_value = "TESTDB"

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        # task needs to allow for runtime arguments
        output = SnowflakeQueriesFromFile().run(
            account="test", user="test", password="test", file_path=sql_file
        )

        # The result is a list because multiple queries are executed
        assert output == ["TESTDB"]
        for call in snowflake_module_connect_method.call_args_list:
            args, kwargs = call
            assert kwargs == dict(
                account="test",
                user="test",
                password="test",
                application="Prefect_SnowflakeQueriesFromFile",
            )

    def test_required_parameters(self):
        # missing account
        with pytest.raises(ValueError):
            SnowflakeQueriesFromFile().run(user="test", password="test")
        # missing user
        with pytest.raises(ValueError):
            SnowflakeQueriesFromFile().run(account="test", password="test")
        # missing password
        with pytest.raises(ValueError):
            SnowflakeQuery().run(account="test", user="test")
        # missing file
        with pytest.raises(ValueError):
            SnowflakeQueriesFromFile().run(account="test", user="test", password="test")

    def test_file_path_must_be_provided(self):
        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )
        with pytest.raises(ValueError, match="A file path must be provided"):
            task.run()

    def test_execute_error_must_pass_through(self, monkeypatch, sql_file):
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting error
        connection.execute_string.side_effect = sf.DatabaseError("Invalid query")

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )

        with pytest.raises(sf.errors.DatabaseError, match="Invalid query"):
            task.run(file_path=sql_file)

    def test_execute_fetchall(self, monkeypatch, sql_file):
        """
        Tests that the SnowflakeQueriesFromFile Task calls the fetchall method on the
        cursor. This is to prevent future code edits from returning the cursor
        object because cursors are not pickleable.
        """
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # link all the mocks together appropriately
        connection.execute_string.return_value = [cursor]

        # setting fetchall return
        cursor.fetchall.return_value = "TESTDB"

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        output = SnowflakeQueriesFromFile(
            account="test", user="test", password="test"
        ).run(file_path=sql_file)

        # The result is a list because multiple queries are executed
        assert output == ["TESTDB"]

    def test_run_method_accepts_alternate_cursor(self, monkeypatch, sql_file):
        """
        Tests that the default cursor used by the Snowflake connection
        is of the type `SnowflakeCursor`, and that the cursor type can
        be overriden by providing a different cursor type to the
        `cursor_type` keyword argument.
        """
        default_cursor = MagicMock(spec=sf.cursor.SnowflakeCursor)
        dict_cursor = MagicMock(spec=sf.cursor.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting fetchall return
        default_cursor.fetchall.return_value = [
            "1",
            "2",
            "3",
        ]
        dict_cursor.fetchall.return_value = {
            "one": "1",
            "two": "2",
            "three": "3",
        }

        # execute_string returns a list of cursors
        def mock_execute_string(
            query, cursor_class: SnowflakeCursor
        ) -> List[SnowflakeCursor]:
            if cursor_class == DictCursor:
                return [dict_cursor]
            else:
                return [default_cursor]

        connection.execute_string = mock_execute_string

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", file_path=sql_file
        )

        default_cursor_output = task.run(cursor_type=SnowflakeCursor)
        dict_cursor_output = task.run(cursor_type=DictCursor)

        assert default_cursor_output == [["1", "2", "3"]]
        assert dict_cursor_output == [{"one": "1", "two": "2", "three": "3"}]
