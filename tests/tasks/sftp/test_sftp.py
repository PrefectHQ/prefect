from unittest.mock import MagicMock
import pytest
from paramiko import Transport, SFTPClient
from prefect.tasks.sftp.sftp import SftpDownload, SftpUpload


@pytest.fixture
def mock_conn(monkeypatch):
    sftp_conn = MagicMock()
    transport = MagicMock(spec=Transport)
    transport.connect = MagicMock(username="test", password="test")
    sftp_client = MagicMock(spec=SFTPClient)
    connection = MagicMock()
    sftp_client.return_value = MagicMock(from_transport=connection)

    monkeypatch.setattr("prefect.tasks.sftp.sftp.SFTPClient", sftp_client)
    monkeypatch.setattr("prefect.tasks.sftp.sftp.Transport", transport)

    return sftp_conn, sftp_client


class TestSftpDownload:
    def test_construction(self):
        """
        Tests that all required params are present for SftpDownload Task.
        """
        task = SftpDownload(
            host="test",
            port_number=22,
            password="test",
            username="test",
            remote_path="test",
        )
        assert task.host == "test"
        assert task.username == "test"
        assert task.password == "test"
        assert task.port_number == 22
        assert task.remote_path == "test"

    def test_required_params(self):
        """
        Tests to check if there are missing required parameters.
        """

        # raises Value error if host name is not provided
        with pytest.raises(ValueError, match="A host name must be provided"):
            SftpDownload().run(
                port_number=22,
                password="test",
                username="test",
                remote_path="foo-home/sftp-test.csv",
            )

        # raises Value error if port_number name is not provided
        with pytest.raises(ValueError, match="A port_number name must be provided"):
            SftpDownload().run(
                host="test",
                password="test",
                username="test",
                remote_path="foo-home/sftp-test.csv",
            )
        # raises Value error if username is not provided
        with pytest.raises(ValueError, match="User name must be provided"):
            SftpDownload().run(
                host="test",
                port_number=22,
                password="test",
                remote_path="foo-home/sftp-test.csv",
            )

        # raises Value error if password is not provided
        with pytest.raises(ValueError, match="A password must be provided"):
            SftpDownload().run(
                host="test",
                port_number=22,
                username="test",
                remote_path="foo-home/sftp-test.csv",
            )

        # raises Value error if remote_path is not provided
        with pytest.raises(ValueError, match="A remote_path must be provided"):
            SftpDownload().run(
                host="test",
                port_number=22,
                password="test",
                username="test",
            )

    # test to check if the ddl/dml query was executed
    def test_execute_download(self, mock_conn):
        """
        Tests that the SftpDownload Task can download a file.
        """
        remote_path = "foo-home/sftp-test.csv"
        connection = mock_conn[0]
        connection().__enter__().get.return_value = True

        sftp_download_task = SftpDownload(
            host="test",
            port_number=22,
            password="test",
            username="test",
            remote_path=remote_path,
        )
        sftp_download_task._connection = connection
        sftp_download_task._connection.get.return_value = True
        sftp_download_task._connection.stat.return_value = True
        sftp_download_task.run()
        sftp_download_task._connection.get.assert_called_once()
        sftp_download_task._connection.stat.assert_called_once()
        connection.assert_called_once()


class TestSftpUpload:
    def test_construction(self):
        """
        Tests that all required params are present for SftpUpload Task.
        """
        task = SftpUpload(
            host="test",
            port_number=22,
            password="test",
            username="test",
            remote_path="test",
            local_path="test",
        )
        assert task.host == "test"
        assert task.username == "test"
        assert task.password == "test"
        assert task.port_number == 22
        assert task.remote_path == "test"
        assert task.local_path == "test"

    def test_required_params(self):
        """
        Tests to check if there are missing required parameters.
        """

        # raises Value error if host name is not provided
        with pytest.raises(ValueError, match="A host name must be provided"):
            SftpUpload().run(
                port_number=22,
                password="test",
                username="test",
                remote_path="foo-home/sftp-test.csv",
                local_path="foo-home/sftp-test.csv",
            )

        # raises Value error if port_number name is not provided
        with pytest.raises(ValueError, match="A port_number name must be provided"):
            SftpUpload().run(
                host="test",
                password="test",
                username="test",
                remote_path="foo-home/sftp-test.csv",
                local_path="foo-home/sftp-test.csv",
            )
        # raises Value error if username is not provided
        with pytest.raises(ValueError, match="User name must be provided"):
            SftpUpload().run(
                host="test",
                port_number=22,
                password="test",
                remote_path="foo-home/sftp-test.csv",
                local_path="foo-home/sftp-test.csv",
            )

        # raises Value error if password is not provided
        with pytest.raises(ValueError, match="A password must be provided"):
            SftpUpload().run(
                host="test",
                port_number=22,
                username="test",
                remote_path="foo-home/sftp-test.csv",
                local_path="foo-home/sftp-test.csv",
            )

        # raises Value error if remote_path is not provided
        with pytest.raises(ValueError, match="A remote_path must be provided"):
            SftpUpload().run(
                host="test",
                port_number=22,
                password="test",
                username="test",
                local_path="foo-home/sftp-test.csv",
            )

        # raises Value error if local_path is not provided
        with pytest.raises(ValueError, match="A local_path must be provided"):
            SftpUpload().run(
                host="test",
                port_number=22,
                password="test",
                username="test",
                remote_path="foo-home/sftp-test.csv",
            )

    # test to check if the ddl/dml query was executed
    def test_execute_upload(self, mock_conn):
        """
        Tests that the SftpUpload Task can download a file.
        """
        connection = mock_conn[0]
        connection().__enter__().put.return_value = True

        sftp_upload_task = SftpUpload(
            host="test",
            port_number=22,
            password="test",
            username="test",
            remote_path="foo-home/sftp-test.csv",
            local_path="foo-home/sftp-test.csv",
        )
        sftp_upload_task._connection = connection

        sftp_upload_task.run()
        connection.assert_called_once()
