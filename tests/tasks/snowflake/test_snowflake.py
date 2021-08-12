from unittest.mock import MagicMock
from snowflake.connector.cursor import SnowflakeCursor, DictCursor

import pytest

import snowflake.connector as sf
from prefect.tasks.snowflake import SnowflakeQuery


class TestSnowflakeQuery:
    def test_construction(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None

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
