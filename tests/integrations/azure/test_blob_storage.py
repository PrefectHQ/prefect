import pytest
from unittest.mock import MagicMock
from pathlib import Path
from prefect_azure.deployments import steps

def test_pull_skips_directories(monkeypatch, tmp_path):
    """
    Test that pull_from_azure_blob_storage skips directory placeholders (blobs ending with '/')
    and only downloads real files.
    """

    # Create mock blob objects
    class MockBlob:
        def __init__(self, name):
            self.name = name

    mock_blobs = [
        MockBlob("folder1/"),   # directory placeholder
        MockBlob("file1.txt"),  # real file
    ]

    # Mock container client
    mock_client = MagicMock()
    mock_client.list_blobs.return_value = mock_blobs
    mock_client.download_blob.return_value.readinto = lambda f: f.write(b"content")

    # Patch get_container_client to return mock client
    monkeypatch.setattr(steps, "ContainerClient", lambda *args, **kwargs: mock_client)

    # Change working directory to tmp_path
    monkeypatch.chdir(tmp_path)

    # Call the function
    result = steps.pull_from_azure_blob_storage("my-container", "prefix", {"connection_string": "fake"})

    # Check that only the file was created
    downloaded_files = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert "file1.txt" in downloaded_files
    assert not any(p.name == "folder1" for p in tmp_path.rglob("*"))
