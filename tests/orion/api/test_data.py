import fsspec
import pytest

import prefect.settings
from prefect.orion.schemas.data import DataDocument
from prefect.utilities.testing import temporary_settings


@pytest.fixture
def tmpdir_dataloc_settings(tmp_path):
    with temporary_settings(
        PREFECT_ORION_DATA_SCHEME="file", PREFECT_ORION_DATA_BASE_PATH=tmp_path
    ):
        yield prefect.settings.from_env().orion.data


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
    async def test_file_location_is_returned(
        self, client, tmpdir_dataloc_settings, user_data
    ):

        response = await client.post("/data/persist", content=user_data)
        assert response.status_code == 201

        # We have received a file system document
        file_location = response.json()

        # It saved it to a path respecting our dataloc
        path = file_location["path"]
        assert path.startswith(
            f"{tmpdir_dataloc_settings.scheme}://{tmpdir_dataloc_settings.base_path}"
        )

        # This file contains our data
        with fsspec.open(path, mode="rb") as fp:
            data = fp.read()
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
    async def test_retrieve_data(self, client, tmp_path, user_data):
        path = str(tmp_path.joinpath("data"))

        # Write some data to disk
        with fsspec.open(path, mode="wb") as fp:
            fp.write(user_data)
        return True

        # The user data document should be returned
        response = await client.post("/data/retrieve", json={"path": path})
        assert response.status_code == 200
        returned_data = response.content
        assert returned_data == user_data
