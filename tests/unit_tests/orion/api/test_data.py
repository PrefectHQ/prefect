import pytest
import os
import base64

from prefect import settings
from prefect.utilities.settings import DataLocationSettings, Settings
from prefect.orion.schemas.data import (
    DataDocument,
    OrionDataDocument,
    FileSystemDataDocument,
    Base64String,
)


@pytest.fixture
def tmpdir_dataloc_settings(tmpdir, monkeypatch):
    new_settings = settings.copy(deep=True).dict()
    new_settings["orion"]["data"] = DataLocationSettings(
        scheme="file",
        base_path=str(tmpdir),
    )
    monkeypatch.setattr("prefect.settings", Settings.parse_obj(new_settings))
    yield settings.orion.data


class TestPersistData:
    @pytest.mark.parametrize(
        "user_data",
        [
            # Test a couple forms of bytes
            DataDocument(encoding="foo", blob=b"hello").json().encode(),
            b"test!",
            bytes([0, 1, 2]),
        ],
    )
    async def test_orion_datadoc_is_returned(
        self, client, tmpdir_dataloc_settings, user_data
    ):

        response = await client.post(
            "/data/persist", json=Base64String.from_bytes(user_data).dict()
        )
        assert response.status_code == 201

        # We have received an orion document
        orion_datadoc = OrionDataDocument.parse_obj(response.json())

        # The blob contains a file system document
        fs_datadoc = orion_datadoc.read()

        # The fs datadoc can be read into our data
        path, data = fs_datadoc.read()
        assert path.startswith(
            f"{tmpdir_dataloc_settings.scheme}://{tmpdir_dataloc_settings.base_path}"
        )
        assert data == user_data


class TestRetrieveData:
    @pytest.mark.parametrize(
        "user_data",
        [
            # Test a couple forms of bytes
            DataDocument(encoding="foo", blob=b"hello").json().encode(),
            b"test!",
            bytes([0, 1, 2]),
        ],
    )
    async def test_retrieve_data(self, client, tmpdir, user_data):
        path = str(tmpdir.join("data"))

        # Create a full Orion data document describing the data and write to disk
        orion_datadoc = OrionDataDocument.create(
            FileSystemDataDocument.create((path, user_data), encoding="file")
        )

        # The user data document should be returned
        response = await client.post(
            "/data/retrieve", json=orion_datadoc.dict(json_compatible=True)
        )
        assert response.status_code == 200
        returned_data = Base64String.parse_obj(response.json()).to_bytes()
        assert returned_data == user_data
