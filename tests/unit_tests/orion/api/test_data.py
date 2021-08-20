import pytest
import os

from prefect import settings
from prefect.utilities.settings import DataLocationSettings, Settings
from prefect.orion.schemas.data import DataDocument


@pytest.fixture
def tmpdir_dataloc_settings(tmpdir, monkeypatch):
    new_settings = settings.copy(deep=True).dict()
    new_settings["orion"]["data"] = DataLocationSettings(
        scheme="file",
        base_path=str(tmpdir),
    )
    monkeypatch.setattr("prefect.settings", Settings.parse_obj(new_settings))
    yield settings.orion.data


class TestPutData:
    async def test_orion_datadoc_is_returned(self, client, tmpdir_dataloc_settings):
        datadoc = DataDocument(encoding="text", blob=b"foo")
        response = await client.post(
            "/data/put", json=datadoc.dict(json_compatible=True)
        )
        assert response.status_code == 201

        # We have received an orion document
        orion_datadoc = DataDocument.parse_obj(response.json())
        assert isinstance(orion_datadoc, DataDocument)
        assert orion_datadoc.encoding == "orion"
        assert orion_datadoc.blob is not None

        # The blob contains a location document
        loc_datadoc = DataDocument.parse_raw(orion_datadoc.blob)
        assert loc_datadoc.encoding == "file"
        assert loc_datadoc.blob.decode().startswith(tmpdir_dataloc_settings.base_path)


class TestGetDataDoc:
    async def test_user_datadoc_is_returned(self, client, tmpdir_dataloc_settings):
        # Write a user data document to disk
        user_datadoc = DataDocument(encoding="foo", blob=b"hello")
        path = os.path.join(tmpdir_dataloc_settings.base_path, "test.data")
        with open(path, "wt") as f:
            f.write(user_datadoc.json())

        # Create a full Orion data document describing the data
        orion_datadoc = DataDocument(
            encoding="orion",
            blob=DataDocument(
                encoding="file",
                blob=path.encode(),
            ).json(),
        )

        # The user data document should be returned
        response = await client.post(
            "/data/get", json=orion_datadoc.dict(json_compatible=True)
        )
        assert response.status_code == 200
        returned_datadoc = DataDocument.parse_obj(response.json())
        assert returned_datadoc == user_datadoc
