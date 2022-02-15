import pytest

import prefect.settings
from prefect.orion.schemas.data import DataDocument
from prefect.utilities.testing import temporary_settings


@pytest.fixture
def tmpdir_dataloc_settings(tmp_path):
    with temporary_settings(
        PREFECT_ORION_DATA_SCHEME="file", PREFECT_ORION_DATA_BASE_PATH=tmp_path
    ):
        yield prefect.settings.from_context().orion.data


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

        response = await client.post("/data/persist", content=user_data)
        assert response.status_code == 201

        # We have received an orion document
        orion_datadoc = DataDocument.parse_obj(response.json())

        # The blob contains a file system document
        fs_datadoc = orion_datadoc.decode()

        # It saved it to a path respecting our dataloc
        path = fs_datadoc.blob.decode()
        assert path.startswith(
            f"{tmpdir_dataloc_settings.scheme}://{tmpdir_dataloc_settings.base_path}"
        )

        # The fs datadoc can be decode into our data
        data = fs_datadoc.decode()
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

        # Create a full Orion data document describing the data and write to disk
        orion_datadoc = DataDocument.encode(
            encoding="orion",
            data=DataDocument.encode(encoding="file", data=user_data, path=path),
        )

        # The user data document should be returned
        response = await client.post(
            "/data/retrieve", json=orion_datadoc.dict(json_compatible=True)
        )
        assert response.status_code == 200
        returned_data = response.content
        assert returned_data == user_data
