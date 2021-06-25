import os
import sys
from unittest.mock import MagicMock

import pytest

from prefect.utilities.filesystems import parse_path, read_bytes_from_path


class Test_parse_path:
    @pytest.mark.parametrize("scheme", [None, "local", "file"])
    def test_local_file_scheme_normalized(self, scheme):
        path = "/path/to/file.txt"
        unparsed = f"{scheme}://{path}" if scheme else path
        parsed = parse_path(unparsed)
        assert parsed.scheme == "file"
        assert parsed.netloc == ""
        assert parsed.path == path

    @pytest.mark.skipif(os.name != "nt", reason="Windows only test")
    @pytest.mark.parametrize(
        "path",
        [
            "c:/path/to/file.txt",
            "c:\\path\\to\\file.txt" "\\path\\to\\file.txt",
        ],
    )
    def test_windows_local_paths(self, path):
        parsed = parse_path(path)
        assert parsed.scheme == "file"
        assert parsed.netloc == ""
        assert parsed.path == path

    def test_all_components(self):
        parsed = parse_path("s3://bucket/path/to/file.txt")
        assert parsed.scheme == "s3"
        assert parsed.netloc == "bucket"
        assert parsed.path == "/path/to/file.txt"


class Test_read_bytes_from_path:
    @pytest.mark.parametrize("scheme", ["agent", None])
    def test_read_local_file(self, tmpdir, scheme):
        if scheme and sys.platform == "win32":
            pytest.skip("Scheme not supported for Windows file paths")

        path = str(tmpdir.join("test.yaml"))
        with open(path, "wb") as f:
            f.write(b"hello")

        path_arg = (
            path
            if scheme is None
            else "agent://" + os.path.splitdrive(path)[1].replace("\\", "/")
        )
        res = read_bytes_from_path(path_arg)
        assert res == b"hello"

    @pytest.mark.parametrize("scheme", ["http", "https"])
    def test_read_http_file(self, monkeypatch, scheme):
        pytest.importorskip("requests")

        url = f"{scheme}://some/file.json"

        requests_get = MagicMock(return_value=MagicMock(content=b"testing"))
        monkeypatch.setattr("requests.get", requests_get)

        res = read_bytes_from_path(url)
        assert requests_get.call_args[0] == (url,)
        assert res == b"testing"

    def test_read_gcs(self, monkeypatch):
        pytest.importorskip("prefect.utilities.gcp")
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.utilities.gcp.get_storage_client", MagicMock(return_value=client)
        )
        res = read_bytes_from_path("gcs://mybucket/path/to/thing.yaml")
        assert client.bucket.call_args[0] == ("mybucket",)
        bucket = client.bucket.return_value
        assert bucket.get_blob.call_args[0] == ("path/to/thing.yaml",)
        blob = bucket.get_blob.return_value
        assert blob.download_as_bytes.called
        assert blob.download_as_bytes.return_value is res

    def test_read_s3(self, monkeypatch):
        pytest.importorskip("prefect.utilities.aws")
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.utilities.aws.get_boto_client", MagicMock(return_value=client)
        )
        res = read_bytes_from_path("s3://mybucket/path/to/thing.yaml")
        assert client.download_fileobj.call_args[1]["Bucket"] == "mybucket"
        assert client.download_fileobj.call_args[1]["Key"] == "path/to/thing.yaml"
        assert isinstance(res, bytes)
