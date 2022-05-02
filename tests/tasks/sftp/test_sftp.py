from unittest.mock import MagicMock
import pytest, socket
from paramiko import Transport, SFTPClient
from tasks.sftp import SftpDownload, SftpUpload


@pytest.fixture
def mock_conn(monkeypatch):
    sftp_conn = MagicMock()
    transport = MagicMock(spec=Transport)
    transport.connect = MagicMock(username="test", password="test")
    sftp_client = MagicMock(spec=SFTPClient)
    connection = MagicMock()
    sftp_client.return_value = MagicMock(from_transport=connection)

    monkeypatch.setattr(
        "tasks.custom_sftp_task.SFTPClient", sftp_client
    )
    monkeypatch.setattr(
        "tasks.custom_sftp_task.Transport", transport
    )

    return sftp_conn


class TestSftpDownload:
    def test_construction(self):
        """
        Tests that all required params are present for SftpDownload Task.
        """
        task = SftpDownload(
            host='test',
            port_number=22,
            password='test',
            username='test',
            remote_path='test'
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
                password='test',
                username='test',
                remote_path='foo-home/sftp-test.csv'
            )

        # raises Value error if port_number name is not provided
        with pytest.raises(ValueError, match="A port_number name must be provided"):
            SftpDownload().run(
                host='test',
                password='test',
                username='test',
                remote_path='foo-home/sftp-test.csv'
            )
        # raises Value error if username is not provided
        with pytest.raises(ValueError, match="User name must be provided"):
            SftpDownload().run(
                host='test',
                port_number=22,
                password='test',
                remote_path='foo-home/sftp-test.csv'
            )

        # raises Value error if password is not provided
        with pytest.raises(ValueError, match="A password must be provided"):
            SftpDownload().run(
                host='test',
                port_number=22,
                username='test',
                remote_path='foo-home/sftp-test.csv'
            )

        # raises Value error if remote_path is not provided
        with pytest.raises(ValueError, match="A remote_path must be provided"):
            SftpDownload().run(
                host='test',
                port_number=22,
                password='test',
                username='test',
            )

    # test to check if the ddl/dml query was executed
    def test_execute_query(self, mock_conn):
        """
        Tests that the SftpDownload Task can download a file.
        """
        remote_path = 'foo-home/sftp-test.csv'
        connection = mock_conn
        connection().__enter__().get.return_value = remote_path

        sftp_download_task = SftpDownload(
            host='test',
            port_number=22,
            password='test',
            username='test',
            remote_path=remote_path
        )
        sftp_download_task._connection = connection

        output = sftp_download_task.run()
        assert output == True

class TestSftpUpload:
    def test_construction(self):
        """
        Tests that all required params are present for SftpDownload Task.
        """
        task = SftpUpload(
            host='test',
            port_number=22,
            password='test',
            username='test',
            remote_path='test'
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
            SftpUpload().run(
                port_number=22,
                password='test',
                username='test',
                remote_path='foo-home/sftp-test.csv',
                local_path = 'foo-home/sftp-test.csv'
            )

        # raises Value error if port_number name is not provided
        with pytest.raises(ValueError, match="A port_number name must be provided"):
            SftpUpload().run(
                host='test',
                password='test',
                username='test',
                remote_path='foo-home/sftp-test.csv',
                local_path = 'foo-home/sftp-test.csv'
            )
        # raises Value error if username is not provided
        with pytest.raises(ValueError, match="User name must be provided"):
            SftpUpload().run(
                host='test',
                port_number=22,
                password='test',
                remote_path='foo-home/sftp-test.csv',
                local_path = 'foo-home/sftp-test.csv'
            )

        # raises Value error if password is not provided
        with pytest.raises(ValueError, match="A password must be provided"):
            SftpUpload().run(
                host='test',
                port_number=22,
                username='test',
                remote_path='foo-home/sftp-test.csv',
                local_path = 'foo-home/sftp-test.csv'
            )

        # raises Value error if remote_path is not provided
        with pytest.raises(ValueError, match="A remote_path must be provided"):
            SftpUpload().run(
                host='test',
                port_number=22,
                password='test',
                username='test',
                local_path='foo-home/sftp-test.csv'
            )

        # raises Value error if local_path is not provided
        with pytest.raises(ValueError, match="A local_path must be provided"):
            SftpUpload().run(
                host='test',
                port_number=22,
                password='test',
                username='test',
                remote_path='foo-home/sftp-test.csv'
            )

    # test to check if the ddl/dml query was executed
    def test_execute_query(self, mock_conn):
        """
        Tests that the SftpDownload Task can download a file.
        """
        connection = mock_conn
        connection().__enter__().get.return_value = remote_path

        sftp_upload_task = SftpDownload(
            host='test',
            port_number=22,
            password='test',
            username='test',
            remote_path='foo-home/sftp-test.csv',
            local_path='foo-home/sftp-test.csv'
        )
        sftp_upload_task._connection = connection

        output = sftp_upload_task.run()
        assert output == True
