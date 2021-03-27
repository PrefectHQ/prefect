from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

from pyarrow import flight
import pyarrow as pa
from typing import Any, Dict


class HttpDremioClientAuthHandler(flight.ClientAuthHandler):
    """
    Client for Dremio authentication.

    Args:
        - username (str): user name used to authenticate
        - password (str): password used to authenticate

    Returns:
        - token (str)
    """

    def __init__(self, username: str, password: str):
        super(flight.ClientAuthHandler, self).__init__()
        self.basic_auth = flight.BasicAuth(username, password)
        self.token = None

    def authenticate(self, outgoing: Any, incoming: Any) -> None:
        auth = self.basic_auth.serialize()
        outgoing.write(auth)
        self.token = incoming.read()

    def get_token(self) -> str:
        return self.token


class DremioFetch(Task):
    """
    Task for fetching results of a query using Dremio Query Engine.

    Args:
        - user (str): user name used to authenticate
        - password (str): password used to authenticate
        - host (str): Dremio host address
        - port (int, optional): port used to connect to FlightClient, defaults to 32010 if not
            provided
        - query (str, optional): query to execute against Dremio
        - **kwargs (Any, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        user: str,
        password: str,
        host: str,
        port: int = 32010,
        query: str = None,
        **kwargs: Any,
    ):
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs("user", "password", "host", "port", "query")
    def run(self, user: str, password: str, host: str, port: int, query: str) -> Dict:
        """
        Task run method. Executes a query against Dremio and fetches results.

        Args:
            - user (str): user name used to authenticate
            - password (str): password used to authenticate
            - host (str): Dremio host address
            - port (int, optional): port used to connect to FlightClient, defaults to 32010 if not
                provided
            - query (str, optional): query to execute against query engine

        Returns:
            - dict: a dictionary of data returned by Dremio

        Raises:
            - ValueError: if `query` is `None`
        """
        if not query:
            raise ValueError("A query string must be provided")

        client = flight.FlightClient(f"grpc+tcp://{host}:{port}")
        client.authenticate(HttpDremioClientAuthHandler(user, password))

        info = client.get_flight_info(
            flight.FlightDescriptor.for_command(query + "--arrow flight")
        )
        reader = client.do_get(info.endpoints[0].ticket)
        batches = []
        while True:
            try:
                batch, _ = reader.read_chunk()
                batches.append(batch)
            except StopIteration:
                break
        data = pa.Table.from_batches(batches)
        return data.to_pydict()
