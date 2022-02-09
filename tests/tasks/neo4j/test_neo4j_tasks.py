from prefect.tasks.neo4j.neo4j_tasks import Neo4jRunCypherQueryTask
from prefect.engine.signals import FAIL
import pytest

from unittest import mock


class TestNeo4jRunCypherQueryTask:
    def test_construction_no_values(self):
        neo4j_task = Neo4jRunCypherQueryTask()

        assert neo4j_task.server_uri is None
        assert neo4j_task.user is None
        assert neo4j_task.password is None
        assert neo4j_task.server_uri_env_var is None
        assert neo4j_task.user_env_var is None
        assert neo4j_task.password_env_var is None
        assert neo4j_task.db_name is None
        assert neo4j_task.db_name_env_var is None
        assert neo4j_task.cypher_query is None
        assert neo4j_task.return_result_as == "raw"

    def test_construction_with_values(self):
        neo4j_task = Neo4jRunCypherQueryTask(
            server_uri="uri",
            user="user",
            password="pwd",
            db_name="db",
            server_uri_env_var="uri_env",
            user_env_var="user_env",
            password_env_var="pwd_env",
            db_name_env_var="db_env",
            cypher_query="query",
            return_result_as="json",
        )

        assert neo4j_task.server_uri == "uri"
        assert neo4j_task.user == "user"
        assert neo4j_task.password == "pwd"
        assert neo4j_task.db_name == "db"
        assert neo4j_task.server_uri_env_var == "uri_env"
        assert neo4j_task.user_env_var == "user_env"
        assert neo4j_task.password_env_var == "pwd_env"
        assert neo4j_task.db_name_env_var == "db_env"
        assert neo4j_task.cypher_query == "query"
        assert neo4j_task.return_result_as == "json"

    def test_run_raises_with_no_server_uri_and_env_var(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = (
            "Please provide either the `server_uri` or the `server_uri_env_var`."
        )
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run()

    def test_run_raises_with_server_uri_env_var_not_found(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "`env_var` not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(server_uri_env_var="env_var")

    def test_run_raises_with_no_user_and_env_var(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "Please provide either the `user` or the `user_env_var`."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(
                server_uri="uri",
            )

    def test_run_raises_with_user_env_var_not_found(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "`env_var` not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(server_uri="uri", user_env_var="env_var")

    def test_run_raises_with_no_password_and_env_var(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "Please provide either the `password` or the `password_env_var`."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(server_uri="uri", user="user")

    def test_run_raises_with_password_env_var_not_found(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "`env_var` not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(server_uri="uri", user="user", password_env_var="env_var")

    def test_run_raises_with_db_name_env_var_not_found(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "`env_var` not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(
                server_uri="uri",
                user="user",
                password="password",
                db_name_env_var="env_var",
            )

    def test_run_raises_with_no_cypher_query(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "Please provide a value for `cypher_query`."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(server_uri="uri", user="user", password="password")

    def test_run_raises_with_illegal_return_result_as(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "Illegal value for `return_result_as`. Illegal value is: illegal."
        with pytest.raises(ValueError, match=msg_match):
            neo4j_task.run(
                server_uri="uri",
                user="user",
                password="password",
                cypher_query="query",
                return_result_as="illegal",
            )

    def test_run_raises_fail_on_neo4j_connect(self):
        neo4j_task = Neo4jRunCypherQueryTask()
        msg_match = "Error while connecting to Neo4j."
        with pytest.raises(FAIL, match=msg_match):
            neo4j_task.run(
                server_uri="bolt://uri:9999",
                user="user",
                password="password",
                cypher_query="query",
            )

    @mock.patch("prefect.tasks.neo4j.neo4j_tasks.Graph")
    @mock.patch("prefect.tasks.neo4j.neo4j_tasks.Graph.run")
    def test_run_raises_fail_on_query_error(self, mock_run, mock_graph):
        class mockRun:
            def data(self):
                return [{"key1": "value1"}, {"key2": "value2"}]

        class mockGraph:
            def run(self):
                return mockRun()

        mock_graph.return_value = mockGraph
        mock_run.run = mockGraph.run
        neo4j_task = Neo4jRunCypherQueryTask()
        result = neo4j_task.run(
            server_uri="bolt://localhost:7687",
            user="neo4j",
            password="s3cr3t",
            cypher_query="query",
        )

        assert result == [{"key1": "value1"}, {"key2": "value2"}]

    @mock.patch("prefect.tasks.neo4j.neo4j_tasks.Graph")
    @mock.patch("prefect.tasks.neo4j.neo4j_tasks.Graph.run")
    def test_run_raises_fail_on_query_error(self, mock_run, mock_graph):
        import pandas as pd

        class mockRun:
            def data(self):
                return [{"key1": "value1"}, {"key2": "value2"}]

            def to_data_frame(self):
                return pd.DataFrame([{"key": "value"}])

        class mockGraph:
            def run(self):
                return mockRun()

        mock_graph.return_value = mockGraph
        mock_run.run = mockGraph.run
        neo4j_task = Neo4jRunCypherQueryTask()
        result = neo4j_task.run(
            server_uri="bolt://localhost:7687",
            user="neo4j",
            password="s3cr3t",
            cypher_query="query",
            return_result_as="dataframe",
        )

        assert result.equals(pd.DataFrame([{"key": "value"}]))
