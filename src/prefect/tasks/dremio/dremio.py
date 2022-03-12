from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

import sys
from pyarrow import flight
import pyarrow as pa
from typing import Any, Dict


class DremioClientAuthMiddlewareFactory(flight.ClientMiddlewareFactory):
    """
    A factory that creates DremioClientAuthMiddleware(s).

    Args:

    Returns:

    """

    def __init__(self):
        self.call_credential = []

    def start_call(self, info):
        return DremioClientAuthMiddleware(self)

    def set_call_credential(self, call_credential):
        self.call_credential = call_credential


class DremioClientAuthMiddleware(flight.ClientMiddleware):
    """
    A ClientMiddleware that extracts the bearer token from
    the authorization header returned by the Dremio
    Flight Server Endpoint.

    Args:
        - factory : ClientHeaderAuthMiddlewareFactory
        The factory to set call credentials if an
        authorization header with bearer token is
        returned by the Dremio server.
    Returns:
        - bearer token
    """

    def __init__(self, factory):
        self.factory = factory

    def received_headers(self, headers):
        auth_header_key = "authorization"
        authorization_header = []
        for key in headers:
            if key.lower() == auth_header_key:
                authorization_header = headers.get(auth_header_key)
        self.factory.set_call_credential(
            [b"authorization", authorization_header[0].encode("utf-8")]
        )


class DremioFetch(Task):
    """
    Task for fetching results of a query using Dremio Query Engine.

    Args:
        - username (str): user name used to authenticate
        - password (str): password used to authenticate
        - hostname (str): Dremio host address
        - flightport (int, optional): port used to connect to FlightClient, defaults to 32010 if not
            provided
        - tls (bool): connect to the server endpoint with an encrypted TLS connection
        - certs (str): path to a certificate
        - query (str, optional): query to execute against Dremio
        - **kwargs (Any, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        username: str = None,
        password: str = None,
        hostname: str = None,
        flightport: int = 32010,
        tls: bool = False,
        certs: str = None,
        query: str = None,
        **kwargs: Any,
    ):
        self.username = username
        self.password = password
        self.hostname = hostname
        self.flightport = flightport
        self.tls = tls
        self.certs = certs
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "username", "password", "hostname", "flightport", "tls", "certs", "query"
    )
    def run(
        self,
        username: str,
        password: str,
        hostname: str,
        flightport: int,
        tls: bool,
        certs: str,
        query: str,
    ) -> Dict:
        """
        Task run method. Executes a query against Dremio and fetches results.

        Args:
            - username (str): user name used to authenticate
            - password (str): password used to authenticate
            - hostname (str): Dremio host address
            - flightport (int, optional): port used to connect to FlightClient, defaults to 32010 if not
                provided
            - tls (bool): connect to the server endpoint with an encrypted TLS connection
            - certs (str): path to a certificate
            - query (str, optional): query to execute against query engine

        Returns:
            - dict: a dictionary of data returned by Dremio

        Raises:
            - ValueError: if `query` is `None`
        """
        if not query:
            raise ValueError("A query string must be provided")
        scheme = "grpc+tcp"
        connection_args = {}

        if tls:
            # Connect to the server endpoint with an encrypted TLS connection.
            self.logger.debug("Enabling TLS connection")
            scheme = "grpc+tls"
            if certs:
                self.logger.debug("Trusted certificates provided")
                # TLS certificates are provided in a list of connection arguments.
                with open(certs, "rb") as root_certs:
                    connection_args["tls_root_certs"] = root_certs.read()
            else:
                self.logger.error(
                    "Trusted certificates must be provided to establish a TLS connection"
                )
                sys.exit()
        else:
            self.logger.info(
                "You are not using a secure connection. Consider setting tls=True"
            )

        # Two WLM settings can be provided upon initial authneitcation
        # with the Dremio Server Flight Endpoint:
        # - routing-tag
        # - routing queue
        initial_options = flight.FlightCallOptions(
            headers=[
                (b"routing-tag", b"test-routing-tag"),
                (b"routing-queue", b"Low Cost User Queries"),
            ]
        )
        client_auth_middleware = DremioClientAuthMiddlewareFactory()
        client = flight.FlightClient(
            "{}://{}:{}".format(scheme, hostname, flightport),
            middleware=[client_auth_middleware],
            **connection_args,
        )

        # Authenticate with the server endpoint.
        bearer_token = client.authenticate_basic_token(
            username, password, initial_options
        )
        self.logger.debug("Authentication was successful. Token is valid for 30 hours.")

        # Retrieve the schema of the result set.
        options = flight.FlightCallOptions(headers=[bearer_token])

        # Get the FlightInfo message to retrieve the Ticket corresponding
        # to the query result set.
        flight_info = client.get_flight_info(
            flight.FlightDescriptor.for_command(query), options
        )
        self.logger.debug("GetFlightInfo was successful")

        # Retrieve the result set as a stream of Arrow record batches.
        reader = client.do_get(flight_info.endpoints[0].ticket, options)
        self.logger.debug("Reading query results from Dremio")

        # batches of data reduce the number of calls to the server

        batches = []
        while True:
            try:
                batch, _ = reader.read_chunk()
                batches.append(batch)
            except StopIteration:
                break
        data = pa.Table.from_batches(batches)

        return data.to_pydict()
