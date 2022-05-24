import os.path
import contextlib
from typing import Optional
from paramiko import Transport, SFTPClient, SFTPError

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SftpDownload(Task):
    """
    Task for downloading files from an SFTP server.
    Downloads remote file into sftp_downloads/ folder by default.

    Args:
        - host (str): Name of the host to use.
        - username (str): Username used to authenticate.
        - password (str): Password used to authenticate.
        - port_number (int): The port to connect to the server.
        - remote_path (str): The remote SFTP file path.
        - local_path (str): The local file path to download file to.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task constructor.

    Raises:
        - ValueError: Raised if a required parameter is not supplied.
        - ClientError: Raised if exception occurs when connecting/downloading from the server.
    """

    def __init__(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
        **kwargs,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_number = port_number
        self.remote_path = remote_path
        self.local_path = local_path
        super().__init__(**kwargs)

    def _create_connection(self) -> Optional[SFTPClient]:
        """
        Initialize the connection with the SFTP server.
        :return: Optional[SFTPClient]
        """
        transport = Transport(sock=(self.host, self.port_number))
        transport.connect(username=self.username, password=self.password)
        # self._connection = SFTPClient.from_transport(transport)
        connection = SFTPClient.from_transport(transport)
        self.logger.info(f"connected to {self.host}, {self.port_number}")
        return connection

    def file_exists(self, remote_path: str, conn: SFTPClient):
        """
        Checks if file exists in remote path or not.

        Args:
            - remote_path (str): Remote file path to check if file exists.
            - conn (SFTPClient): The connection object for the SFTP server.

        """
        try:
            self.logger.info(f"remote path : {remote_path}")
            conn.stat(remote_path)
        except SFTPError as e:
            self.logger.debug(
                f"The specified file on this '{remote_path}' remote_path does not exist."
            )
            raise e

    @defaults_from_attrs(
        "host", "username", "password", "port_number", "remote_path", "local_path"
    )
    def run(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
    ):
        """
        Task for downloading files from an SFTP server.

        Args:
            - host (str): Name of the host to use.
            - username (str): Username used to authenticate.
            - password (str): Password used to authenticate.
            - port_number (int): The port to connect to the server.
            - remote_path (str): The remote SFTP file path.
            - local_path (str): The local file path to download file to.

        Raises:
            - ValueError: Raised if a required parameter is not supplied.
            - ClientError: Raised if exception occurs when connecting/downloading from the server.
        """
        if not host:
            raise ValueError("A host name must be provided")
        if not username:
            raise ValueError("User name must be provided")
        if not password:
            raise ValueError("A password must be provided")
        if not port_number:
            raise ValueError("A port_number name must be provided")
        if not remote_path:
            raise ValueError("A remote_path must be provided")

        # set default to local path if arg not provided
        self.local_path = (
            "sftp_downloads/" + remote_path.split("/")[-1]
            if local_path is None
            else local_path
        )

        # check if local path exists or not
        local_dir = "/".join(self.local_path.split("/")[:-1]) + "/"
        if not os.path.isdir(local_dir):
            os.mkdir(local_dir)

        with contextlib.closing(self._create_connection()) as conn:
            self.file_exists(remote_path, conn)
            conn.get(remote_path, local_path, callback=None)


class SftpUpload(Task):
    """
    Task for uploading files to an SFTP server.

    Args:
        - host (str): Name of the host to use.
        - username (str): Username used to authenticate.
        - password (str): Password used to authenticate.
        - port_number (int): The port number to connect to the server.
        - remote_path (str): The remote SFTP file path.
        - local_path (str): The local file path to from upload.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the Task constructor.

    Raises:
        - ValueError: Raised if a required parameter is not supplied.
        - ClientError: Raised if exception occurs when connecting/uploading to the server.
    """

    def __init__(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
        **kwargs,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_number = port_number
        self.remote_path = remote_path
        self.local_path = local_path
        super().__init__(**kwargs)

    def _create_connection(self) -> Optional[SFTPClient]:
        """
        Initialize the connection with the SFTP server.
        :return: Optional[SFTPClient]
        """
        transport = Transport(sock=(self.host, self.port_number))
        transport.connect(username=self.username, password=self.password)
        connection = SFTPClient.from_transport(transport)
        self.logger.info(f"connected to {self.host}, {self.port_number}")
        return connection

    @defaults_from_attrs(
        "host", "username", "password", "port_number", "remote_path", "local_path"
    )
    def run(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
    ):
        """
        Task for uploading files to an SFTP server.

        Args:
            - host (str): Name of the host to use.
            - username (str): Username used to authenticate.
            - password (str): Password used to authenticate.
            - port_number (int): The port number to connect to the server.
            - remote_path (str): The remote SFTP file path.
            - local_path (str): The local file path to upload from.

        Raises:
            - ValueError: Raised if a required parameter is not supplied.
            - ClientError: Raised if exception occurs when connecting/uploading from the server.
        """
        if not host:
            raise ValueError("A host name must be provided")
        if not username:
            raise ValueError("User name must be provided")
        if not password:
            raise ValueError("A password must be provided")
        if not port_number:
            raise ValueError("A port_number name must be provided")
        if not remote_path:
            raise ValueError("A remote_path must be provided")
        if not local_path:
            raise ValueError("A local_path must be provided")

        with contextlib.closing(self._create_connection()) as conn:
            conn.put(
                localpath=local_path,
                remotepath=remote_path,
                confirm=True,
            )
