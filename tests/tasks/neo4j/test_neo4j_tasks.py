from prefect.tasks.neo4j.neo4j_tasks import Neo4jRunCypherQueryTask


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
