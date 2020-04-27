import pytest

from prefect.tasks.postgres import PostgresExecute, PostgresFetch


class TestPostgresExecute:
    def test_construction(self):
        task = PostgresExecute(
            db_name="test", user="test", password="test", host="test"
        )
        assert task.commit is False

    def test_query_string_must_be_provided(self):
        task = PostgresExecute(
            db_name="test", user="test", password="test", host="test"
        )
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()


class TestPostgresFetch:
    def test_construction(self):
        task = PostgresFetch(db_name="test", user="test", password="test", host="test")
        assert task.fetch == "one"

    def test_query_string_must_be_provided(self):
        task = PostgresFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_bad_fetch_param_raises(self):
        task = PostgresFetch(db_name="test", user="test", password="test", host="test")
        with pytest.raises(
            ValueError,
            match=r"The 'fetch' parameter must be one of the following - \('one', 'many', 'all'\)",
        ):
            task.run(query="SELECT * FROM some_table", fetch="not a valid parameter")
