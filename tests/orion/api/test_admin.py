import prefect
from prefect.orion import models


async def test_hello_world(client):
    response = await client.get("/admin/hello")
    assert response.status_code == 200
    assert response.json() == "👋"


async def test_version(client):
    response = await client.get("/admin/version")
    assert response.status_code == 200
    assert prefect.__version__
    assert response.json() == prefect.__version__


class TestSettings:
    async def test_read_settings(self, client):
        response = await client.get("/admin/settings")
        assert response.status_code == 200
        parsed_settings = prefect.utilities.settings.Settings.parse_obj(
            response.json()
        ).dict()
        prefect_settings = prefect.settings.copy().dict()

        # remove secret strings because they break equality
        del parsed_settings["orion"]["database"]["connection_url"]
        del prefect_settings["orion"]["database"]["connection_url"]

        assert parsed_settings == prefect_settings


class TestDatabaseAdmin:
    async def test_clear_database(
        self, flow, flow_run, task_run, deployment, session, client
    ):
        for count in [
            models.flows.count_flows,
            models.flow_runs.count_flow_runs,
            models.task_runs.count_task_runs,
            models.deployments.count_deployments,
        ]:
            assert await count(session) > 0

        response = await client.post("/admin/database/clear", json=dict(confirm=True))
        assert response.status_code == 204

        for count in [
            models.flows.count_flows,
            models.flow_runs.count_flow_runs,
            models.task_runs.count_task_runs,
            models.deployments.count_deployments,
        ]:
            assert await count(session) == 0

    async def test_clear_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/clear")
        assert response.status_code == 400

        response = await client.post("/admin/database/clear", json=dict(confirm=False))
        assert response.status_code == 400

    async def test_drop_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/drop")
        assert response.status_code == 400

        response = await client.post("/admin/database/drop", json=dict(confirm=False))
        assert response.status_code == 400

    async def test_create_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/create")
        assert response.status_code == 400

        response = await client.post("/admin/database/create", json=dict(confirm=False))
        assert response.status_code == 400
