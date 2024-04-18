import uuid
from io import BytesIO
from pathlib import Path

import pytest
from azure.core.exceptions import ResourceExistsError
from prefect_azure.blob_storage import (
    AzureBlobStorageContainer,
    blob_storage_download,
    blob_storage_list,
    blob_storage_upload,
)

from prefect import flow


async def test_blob_storage_download_flow(blob_storage_credentials):
    @flow
    async def blob_storage_download_flow():
        return await blob_storage_download(
            container="prefect",
            blob="prefect.txt",
            blob_storage_credentials=blob_storage_credentials,
        )

    data = await blob_storage_download_flow()
    assert data.decode() == "prefect_works"


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


@pytest.mark.parametrize("blob_expected", [None, "prefect.txt", "prefect_new.txt"])
async def test_blob_storage_upload_flow(blob_expected, blob_storage_credentials):
    @flow
    async def blob_storage_upload_flow():
        return await blob_storage_upload(
            b"prefect_works",
            container="prefect",
            blob=blob_expected,
            overwrite=True,
            blob_storage_credentials=blob_storage_credentials,
        )

    blob_result = await blob_storage_upload_flow()
    if blob_expected is None:
        is_valid_uuid(blob_expected)
    else:
        assert blob_expected == blob_result


async def test_blob_storage_upload_blob_exists_flow(
    blob_storage_credentials,
):
    @flow
    async def blob_storage_upload_flow():
        return await blob_storage_upload(
            b"prefect_works",
            container="prefect",
            blob="prefect.txt",
            overwrite=False,
            blob_storage_credentials=blob_storage_credentials,
        )

    with pytest.raises(ResourceExistsError):
        (await blob_storage_upload_flow())


async def test_blob_storage_list_flow(blob_storage_credentials):
    @flow
    async def blob_storage_list_flow():
        return await blob_storage_list(
            container="prefect",
            blob_storage_credentials=blob_storage_credentials,
        )

    blobs = await blob_storage_list_flow()
    assert blobs == [
        {"name": "fakefolder", "metadata": None},
        *[{"name": f"fakefolder/file{i}", "metadata": None} for i in range(4)],
    ]


async def test_blob_storage_list_flow_with_name(blob_storage_credentials):
    @flow
    async def blob_storage_list_flow():
        return await blob_storage_list(
            container="prefect",
            blob_storage_credentials=blob_storage_credentials,
            name_starts_with="fakefolder/",
        )

    blobs = await blob_storage_list_flow()
    assert blobs == [
        {"name": f"fakefolder/file{i}", "metadata": None} for i in range(4)
    ]


async def test_blob_storage_list_flow_with_include(blob_storage_credentials):
    @flow
    async def blob_storage_list_flow():
        return await blob_storage_list(
            container="prefect",
            blob_storage_credentials=blob_storage_credentials,
            include=["metadata"],
        )

    blobs = await blob_storage_list_flow()
    assert len(blobs) == 5
    for blob_data in blobs:
        assert isinstance(blob_data["metadata"], dict)


class TestAzureBlobStorageContainer:
    async def test_download_folder_to_path(
        self, mock_blob_storage_credentials, tmp_path
    ):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        await container.download_folder_to_path("folder", tmp_path / "folder")

        assert (tmp_path / "folder").exists()
        assert (tmp_path / "folder" / "prefect.txt").exists()
        with open(tmp_path / "folder" / "prefect.txt", "rb") as f:
            assert f.read() == b"prefect_works"

    async def test_download_object_to_file_object(
        self, mock_blob_storage_credentials, tmp_path
    ):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        file_path = tmp_path / "file.txt"
        with open(file_path, "wb") as f:
            await container.download_object_to_file_object(
                from_path="prefect.txt", to_file_object=f
            )

        assert file_path.exists()
        with open(file_path, "rb") as f:
            assert f.read() == b"prefect_works"

    async def test_download_object_to_path(
        self, mock_blob_storage_credentials, tmp_path
    ):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        from_path = "prefect.txt"
        to_path = tmp_path / "file.txt"

        await container.download_object_to_path(from_path, to_path)

        assert to_path.exists()
        with open(to_path, "rb") as f:
            assert f.read() == b"prefect_works"

    async def test_upload_from_file_object(
        self, mock_blob_storage_credentials, tmp_path
    ):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        file_content = b"prefect_works_again"
        file_object = BytesIO(file_content)
        to_path = "object"

        uploaded_path = await container.upload_from_file_object(
            from_file_object=file_object,
            to_path=to_path,
        )

        assert uploaded_path == to_path

        await container.download_object_to_path("object", tmp_path / "file.txt")

        with open(tmp_path / "file.txt", "rb") as f:
            assert f.read() == b"prefect_works_again"

    async def test_upload_from_path(self, mock_blob_storage_credentials, tmp_path):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        from_path = tmp_path / "file.txt"
        to_path = "object-from-path"

        with open(from_path, "wb") as f:
            f.write(b"prefect_works_yet_again")

        uploaded_path = await container.upload_from_path(
            from_path=from_path,
            to_path=to_path,
        )

        assert uploaded_path == to_path

        await container.download_object_to_path(to_path, tmp_path / "file.txt")

        with open(tmp_path / "file.txt", "rb") as f:
            assert f.read() == b"prefect_works_yet_again"

    async def test_upload_from_folder(
        self, mock_blob_storage_credentials, tmp_path: Path
    ):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        from_folder = tmp_path / "local_folder"
        from_folder.mkdir(parents=True, exist_ok=True)
        to_folder = "folder"

        file1_path = from_folder / "file1.txt"
        file2_path = from_folder / "file2.txt"
        file1_path.write_bytes(b"file1_content")
        file2_path.write_bytes(b"file2_content")

        await container.upload_from_folder(
            from_folder=from_folder,
            to_folder=to_folder,
        )

        await container.download_object_to_path(
            "folder/file1.txt", tmp_path / "read_file1.txt"
        )

        with open(tmp_path / "read_file1.txt", "rb") as f:
            assert f.read() == b"file1_content"

        await container.download_object_to_path(
            "folder/file2.txt", tmp_path / "read_file2.txt"
        )

        with open(tmp_path / "read_file2.txt", "rb") as f:
            assert f.read() == b"file2_content"

    async def test_get_directory(slef, mock_blob_storage_credentials, tmp_path):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        from_path = "folder"
        local_path = str(tmp_path / "local_directory")

        await container.get_directory(from_path, local_path)

        assert (tmp_path / "local_directory").exists()
        assert (tmp_path / "local_directory" / "prefect.txt").exists()
        with open(tmp_path / "local_directory" / "prefect.txt", "rb") as f:
            assert f.read() == b"prefect_works"

    async def test_put_directory(self, mock_blob_storage_credentials, tmp_path):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        local_path = tmp_path / "local_directory"
        to_path = "destination_directory"

        local_path.mkdir()
        file1_path = local_path / "file1.txt"
        file2_path = local_path / "file2.txt"
        file1_path.write_bytes(b"file1_content")
        file2_path.write_bytes(b"file2_content")

        await container.put_directory(local_path=str(local_path), to_path=to_path)

        await container.download_object_to_path(
            "destination_directory/file1.txt", tmp_path / "read_file1.txt"
        )
        with open(tmp_path / "read_file1.txt", "rb") as f:
            assert f.read() == b"file1_content"

        await container.download_object_to_path(
            "destination_directory/file2.txt", tmp_path / "read_file2.txt"
        )
        with open(tmp_path / "read_file2.txt", "rb") as f:
            assert f.read() == b"file2_content"

    async def test_read_path(self, mock_blob_storage_credentials):
        container = AzureBlobStorageContainer(
            container_name="container",
            credentials=mock_blob_storage_credentials,
        )
        path = "file.txt"
        file_content = b"prefect_works"
        await container.upload_from_file_object(BytesIO(file_content), path)

        result = await container.read_path(path)

        assert result == file_content

    async def test_blob_storage_write_path(self, mock_blob_storage_credentials):
        container = AzureBlobStorageContainer(
            container_name="prefect",
            credentials=mock_blob_storage_credentials,
        )
        await container.write_path("prefect-write-path.txt", b"write_path_works")

        result = await container.read_path("prefect-write-path.txt")

        assert result == b"write_path_works"
