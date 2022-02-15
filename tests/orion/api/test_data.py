import fsspec
import pytest

from fastapi import HTTPException
import prefect.settings
from pathlib import PosixPath
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
    async def test_persisting_and_retrieving_data(
        self, client, tmpdir_dataloc_settings, user_data
    ):

        persist_response = await client.post("/data/persist", content=user_data)
        assert persist_response.status_code == 201

        # We have received a file identifier
        file_identifier = persist_response.json()

        # The file identifier obscures information about the actual file location
        assert len(PosixPath(file_identifier["id"]).parts) == 1

        # This identifier can be used to retrieve data
        retrieve_response = await client.post("/data/retrieve", json=file_identifier)
        assert retrieve_response.status_code == 200
        returned_data = retrieve_response.content
        assert returned_data == user_data

    async def test_retrieving_data_cannot_receive_complex_paths(
        self, client, tmpdir_dataloc_settings
    ):
        malicious_file_identifier = {"id": "../../file-i-shouldnt-access"}

        response = await client.post("/data/retrieve", json=malicious_file_identifier)
        assert response.status_code == 403
