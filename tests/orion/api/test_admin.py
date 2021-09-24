import prefect


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


class TestClearDatabase:
    async def test_clear_database(self, flow, flow_run, task_run, deployment, client):
        for route_prefix in ("/flows", "/flow_runs", "/task_runs", "/deployments"):
            response = await client.post(f"{route_prefix}/count")
            assert response.json() > 0

        response = await client.delete("/admin/universe")
        assert response.status_code == 204

        for route_prefix in ("/flows", "/flow_runs", "/task_runs", "/deployments"):
            response = await client.post(f"{route_prefix}/count")
            assert response.json() == 0
