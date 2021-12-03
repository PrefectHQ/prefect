from unittest.mock import MagicMock

import pytest
import firebolt.db.connection as fb_conn

from prefect.tasks.firebolt.firebolt import FireboltQuery, FireboltQueryGetData


class TestFireboltQuery:
    def test_construction(self):
        task = FireboltQuery(
            database="test", username="test", password="test", engine_name="test", api_endpoint="test", query="test"
        )
        assert task.engine_url is None

    # raises Value error if engine name is not provided
    def test_engine_name_not_provided(self):
        task = FireboltQuery(database="test", username="test", password="test",
                             engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="An engine name must be provided"):
            task.run()

    # raises Value error if database name is not provided
    def test_database_not_provided(self):
        task = FireboltQuery(username="test", password="test", engine_name="test",
                             engine_url=None, api_endpoint="test", query="test")
        with pytest.raises( ValueError, match="A database name must be provided"):
            task.run()

    # raises Value error if username is not provided
    def test_username_not_provided(self):
        task = FireboltQuery(database="test", password="test", engine_name="test",
                             engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="User name must be provided"):
            task.run()

    # raises Value error if password is not provided
    def test_password_not_provided(self):
        task = FireboltQuery(database="test", username="test", engine_name="test",
                             engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="A password must be provided"):
            task.run()

    # raises Value error if api_endpoint is not provided
    def test_api_endpoint_not_provided(self):
        task = FireboltQuery(database="test", username="test", password="test", engine_name="test",
                             engine_url=None, query="test")
        with pytest.raises(ValueError, match="An api endpoint must be provided"):
            task.run()

    # raises Value error if query is not provided
    def test_query_not_provided(self):
        task = FireboltQuery(database="test", username="test", password="test", engine_name="test",
                             engine_url=None, api_endpoint="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_query(self, monkeypatch):
        """
        Tests that the FireboltQuery Task calls the execute method on the cursor.
        """
        firebolt_conn = MagicMock()
        connection = MagicMock(spec=fb_conn.Connection)
        cursor = MagicMock(spec=fb_conn.Cursor)

        # link all the mocks together appropriately
        firebolt_conn.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value = [
            "TESTDB"
        ]

        firebolt_connection = MagicMock(connect=firebolt_conn)

        monkeypatch.setattr(
            "prefect.tasks.firebolt.firebolt.firebolt_conn", firebolt_connection
        )

        query = "SHOW DATABASES"

        output = FireboltQuery(database="test", username="test", password="test", engine_name="test",
                      engine_url=None, api_endpoint="test", query=query).run()

        assert output == ["TESTDB"]


class TestFireboltQueryGetData():
    def test_construction(self):
        task = FireboltQueryGetData(
            database="test", username="test", password="test", engine_name="test", api_endpoint="test", query="test"
        )
        assert task.engine_url is None

    # raises Value error if engine name is not provided
    def test_engine_name_not_provided(self):
        task = FireboltQueryGetData(database="test", username="test", password="test",
                                    engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="An engine name must be provided"):
            task.run()

    # raises Value error if database name is not provided
    def test_database_not_provided(self):
        task = FireboltQueryGetData(username="test", password="test", engine_name="test",
                                    engine_url=None, api_endpoint="test", query="test")
        with pytest.raises( ValueError, match="A database name must be provided"):
            task.run()

    # raises Value error if username is not provided
    def test_username_not_provided(self):
        task = FireboltQueryGetData(database="test", password="test", engine_name="test",
                                    engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="User name must be provided"):
            task.run()

    # raises Value error if password is not provided
    def test_password_not_provided(self):
        task = FireboltQueryGetData(database="test", username="test", engine_name="test",
                                    engine_url=None, api_endpoint="test", query="test")
        with pytest.raises(ValueError, match="A password must be provided"):
            task.run()

    # raises Value error if api_endpoint is not provided
    def test_api_endpoint_not_provided(self):
        task = FireboltQueryGetData(database="test", username="test", password="test", engine_name="test",
                                    engine_url=None, query="test")
        with pytest.raises(ValueError, match="An api endpoint must be provided"):
            task.run()

    # raises Value error if query is not provided
    def test_query_not_provided(self):
        task = FireboltQueryGetData(database="test", username="test", password="test", engine_name="test",
                                    engine_url=None, api_endpoint="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_fetchall(self, monkeypatch):
        """
        Tests that the FireboltQuery Task calls the fetchall method on the cursor.
        """

        firebolt_conn = MagicMock()
        connection = MagicMock(spec=fb_conn.Connection)
        cursor = MagicMock(spec=fb_conn.Cursor)

        # link all the mocks together appropriately
        firebolt_conn.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.fetchall.return_value = [
            "TESTDB"
        ]

        firebolt_connection = MagicMock(connect=firebolt_conn)

        monkeypatch.setattr(
            "prefect.tasks.firebolt.firebolt.firebolt_conn", firebolt_connection
        )

        query = "SHOW DATABASES"

        output = FireboltQueryGetData(database="test", username="test", password="test", engine_name="test",
                                      engine_url=None, api_endpoint="test", query=query).run()
        assert output == ["TESTDB"]
