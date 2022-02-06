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