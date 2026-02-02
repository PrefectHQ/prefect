import httpx
from starlette import status

import prefect


async def test_version(client: httpx.AsyncClient) -> None:
    response = await client.get("/admin/version")
    assert response.status_code == status.HTTP_200_OK
    assert prefect.__version__
    assert response.json() == prefect.__version__


class TestSettings:
    async def test_read_settings(self, client: httpx.AsyncClient) -> None:
        from prefect.settings import Settings, get_current_settings

        response = await client.get("/admin/settings")
        assert response.status_code == status.HTTP_200_OK
        parsed_settings = Settings.model_validate(response.json())
        prefect_settings = get_current_settings()

        assert parsed_settings.model_dump(mode="json") == prefect_settings.model_dump(
            mode="json"
        )
