import errno, time
import os.path
from paramiko import Transport, SFTPClient

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SftpDownload(Task):
    """
    Task for downloading files from an SFTP server.
    Downloads remote file into sftp_downloads/ folder by default

    Args:
        - host (str): name of the host to use.
        - username (str): username used to authenticate.
        - password (str): password used to authenticate.
        - port_number (int): the port number to connect to the server.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.

    Raises:
        - ValueError: if a required parameter is not supplied.
        - ClientError: if exception occurs when connecting/downloading from the server.
    """

    def __init__(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
        **kwargs
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_number = port_number
        self.remote_path = remote_path
        self.local_path = local_path
        super().__init__(**kwargs)

    def _create_connection(self) -> None:
        """
        Initialise the connection with the SFTP server
        :return: None
        """
        transport = Transport(sock=(self.host, self.port_number))
        transport.connect(username=self.username, password=self.password)
        self._connection = SFTPClient.from_transport(transport)
        print("connected to ", self.host, self.port_number)

    def file_exists(self, remote_path) -> bool:
        """
        Checks if file exists in remote path or not.
        :param remote_path:
        :return:

        Raises:
            - IOError: in case of incorrect file name or location.
        """
        try:
            print("remote path : ", remote_path)
            self._connection.stat(remote_path)
        except IOError as e:
            if e.errno == errno.ENOENT:
                return False
            raise
        else:
            return True

    def download(self, remote_path, local_path, retry=5) -> bool:
        """
        Downloads file/files from the specified remote_path to a local_path
        :param remote_path:
        :param local_path:
        :param retry:
        :return bool: True/False
        """
        # first check if local path exists or not
        local_dir = "/".join(local_path.split("/")[:-1]) + "/"
        if not os.path.isdir(local_dir):
            os.mkdir(local_dir)

        # check remote_path
        if self.file_exists(remote_path) or retry == 0:
            self._connection.get(remote_path, local_path, callback=None)
            return True
        elif retry > 0:
            time.sleep(5)
            retry = retry - 1
            self.download(remote_path, local_path, retry=retry)

        return False

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
    ) -> bool:
        """
        Task for downloading files from an SFTP server.

        Args:
            - host (str): name of the host to use.
            - username (str): username used to authenticate.
            - password (str): password used to authenticate.
            - port_number (int): the port number to connect to the server.
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.

        Raises:
            - ValueError: if a required parameter is not supplied.
            - ClientError: if exception occurs when connecting/downloading from the server.
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

        # first init connection to SFTP server
        self._create_connection()

        # download specified file/files
        result = self.download(self.remote_path, self.local_path)

        # close sftp server connection
        self._connection.close()

        return result


class SftpUpload(Task):
    """
    Task for uploading files to an SFTP server.

    Args:
        - host (str): name of the host to use.
        - username (str): username used to authenticate.
        - password (str): password used to authenticate.
        - port_number (int): the port number to connect to the server.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.

    Raises:
        - ValueError: if a required parameter is not supplied.
        - ClientError: if exception occurs when connecting/uploading to the server.
    """

    def __init__(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port_number: int = None,
        remote_path: str = None,
        local_path: str = None,
        **kwargs
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_number = port_number
        self.remote_path = remote_path
        self.local_path = local_path
        super().__init__(**kwargs)

    def _create_connection(self) -> None:
        """
        Initialise the connection with the SFTP server
        :return: None
        """
        transport = Transport(sock=(self.host, self.port_number))
        transport.connect(username=self.username, password=self.password)
        self._connection = SFTPClient.from_transport(transport)
        print("connected to ", self.host, self.port_number)

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
    ) -> bool:
        """
        Task for uploading files to an SFTP server.

        Args:
            - host (str): name of the host to use.
            - username (str): username used to authenticate.
            - password (str): password used to authenticate.
            - port_number (int): the port number to connect to the server.
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.

        Raises:
            - ValueError: if a required parameter is not supplied.
            - ClientError: if exception occurs when connecting/downloading from the server.
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

        # first init connection to SFTP server
        self._create_connection()

        # download specified file/files
        result = self.upload(self.local_path, self.remote_path)

        # close sftp server connection
        self._connection.close()

        return result

    def upload(self, local_path, remote_path):
        if self._connection is None:
            self._create_connection()

        try:
            self._connection.put(
                localpath=local_path,
                remotepath=remote_path,
                confirm=True,
            )
            return True
        except IOError as e:
            print(str(e))
            return False
