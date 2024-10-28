from starlette import status

import prefect
from prefect.server import models


async def test_version(client):
    response = await client.get("/admin/version")
    assert response.status_code == status.HTTP_200_OK
    assert prefect.__version__
    assert response.json() == prefect.__version__


class TestSettings:
    async def test_read_settings(self, client):
        from prefect.settings import Settings, get_current_settings

        response = await client.get("/admin/settings")
        assert response.status_code == status.HTTP_200_OK
        parsed_settings = Settings.model_validate(response.json())
        prefect_settings = get_current_settings()

        assert parsed_settings.model_dump(mode="json") == prefect_settings.model_dump(
            mode="json"
        )


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
        assert response.status_code == status.HTTP_204_NO_CONTENT

        for count in [
            models.flows.count_flows,
            models.flow_runs.count_flow_runs,
            models.task_runs.count_task_runs,
            models.deployments.count_deployments,
        ]:
            assert await count(session) == 0

    async def test_clear_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/clear")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = await client.post("/admin/database/clear", json=dict(confirm=False))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_drop_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/drop")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = await client.post("/admin/database/drop", json=dict(confirm=False))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_database_requires_confirmation(self, client):
        response = await client.post("/admin/database/create")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = await client.post("/admin/database/create", json=dict(confirm=False))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
