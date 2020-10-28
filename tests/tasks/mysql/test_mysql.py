import pytest
import pymysql

from prefect.tasks.mysql.mysql import MySQLExecute, MySQLFetch


class TestMySQLExecute:
    def test_construction(self):
        task = MySQLExecute(db_name="test", user="test", password="test", host="test")
        assert (task.commit is False) and (task.charset == "utf8mb4")

    def test_query_string_must_be_provided(self):
        task = MySQLExecute(db_name="test", user="test", password="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()


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
            match="The 'fetch' parameter must be one of the following - \('one', 'many', 'all'\)",
        ):
            task.run(query="SELECT * FROM some_table", fetch="not a valid parameter")

    def test_construction_with_cursor_type_str(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test", cursor_type='dictcursor')
        assert task.cursor_type == "dictcursor"

    def test_construction_with_cursor_type_class(self):
        task = MySQLFetch(db_name="test", user="test", password="test", host="test", cursor_type=pymysql.cursors.DictCursor)
        assert task.cursor_type == pymysql.cursors.DictCursor

    def test_unsupported_cursor_type_str_param_raises(self):
        cursor_type = "sscursor"
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            TypeError,
            match=f"'cursor_type' should be one of \('cursor', 'dictcursor'\) or the callable equivalent, got {cursor_type}",
        ):
            task.run(query="SELECT * FROM some_table", cursor_type=cursor_type)

    def test_unsupported_cursor_type_class_param_raises(self):
        cursor_type = pymysql.cursors.SSCursor
        task = MySQLFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            TypeError,
            match=f"'cursor_type' should be one of \('cursor', 'dictcursor'\) or the callable equivalent, got {cursor_type}",
        ):
            task.run(query="SELECT * FROM some_table", cursor_type=pymysql.cursors.SSCursor)
